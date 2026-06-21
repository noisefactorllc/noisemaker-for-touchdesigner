"""resources.py — liveness analysis + linear-scan texture pooling. 1:1 port of hlsl
Compiler/Lang/Resources.cs (shaders/src/runtime/resources.js, reference/04 §1).

allocate_resources(passes) maps virtual pooled texIds -> physical slots "phys_N", the producer
of RenderGraph.allocations. PARITY-CRITICAL (reference/04 §1.3): output allocation (insertion
order of pass.outputs values) happens BEFORE input release (pass.inputs values) within a pass;
the free-slot search picks the FIRST freeList entry with availableAfter < i; only 'global_' ids
are excluded (infinite-lived). Fully deterministic, no float math.
"""


def _analyze_liveness(passes):
    lifetime = {}  # texId -> [start, end]

    def touch(tex_id, index):
        if not tex_id:
            return
        if tex_id.startswith('global_'):
            return
        l = lifetime.get(tex_id)
        if l is None:
            lifetime[tex_id] = [index, index]
        else:
            if index < l[0]:
                l[0] = index
            if index > l[1]:
                l[1] = index

    for index, pass_ in enumerate(passes):
        for tex in (pass_.get('inputs') or {}).values():
            touch(tex, index)
        for tex in (pass_.get('outputs') or {}).values():
            touch(tex, index)
    return lifetime


def allocate_resources(passes):
    lifetime = _analyze_liveness(passes)
    allocations = {}            # texId -> "phys_N" (insertion-ordered)
    free_list = []              # list of [phys_id, available_after]
    physical_count = 0

    for i, pass_ in enumerate(passes):
        # 1. allocate outputs (definitions)
        for tex_id in (pass_.get('outputs') or {}).values():
            if tex_id is None:
                continue
            if tex_id.startswith('global_'):
                continue
            if tex_id in allocations:
                continue
            free_idx = -1
            for k in range(len(free_list)):
                if free_list[k][1] < i:
                    free_idx = k
                    break
            if free_idx != -1:
                phys_id = free_list.pop(free_idx)[0]
                allocations[tex_id] = phys_id
            else:
                allocations[tex_id] = 'phys_%d' % physical_count
                physical_count += 1

        # 2. release inputs (last uses)
        for tex_id in (pass_.get('inputs') or {}).values():
            if tex_id is None:
                continue
            if tex_id.startswith('global_'):
                continue
            l = lifetime.get(tex_id)
            if l is not None and l[1] == i:
                phys = allocations.get(tex_id)
                if phys is not None:
                    free_list.append([phys, i])
    return allocations
