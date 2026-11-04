"""Explicit task clauses and source-bound action assessment. No model prose or labels.

The parser is deliberately small. Unsupported/conditional/negative instructions
are retained, not guessed away. Pixels, SAM track names and Muse suggestions do
not create decisive action predicates. Articulation measurements can be supplied
only by a trusted, independently checked adapter; today's SAM adapter supplies none.
"""
from __future__ import annotations

import math
import re
from urllib.parse import unquote


def parse_task(description: str, object_concept: str, destination: str):
    import task_criteria as tc
    clauses = [s.strip(' ,') for s in re.split(r'[,.;\n]|\b(?:and\s+)?then\b|\band\b', description, flags=re.I) if s.strip(' ,')]
    criteria = []
    for i, clause in enumerate(clauses):
        text = re.sub(r'^please\s+', '', clause, flags=re.I)
        # Do not erase negation, conditions, temporal dependencies or alternatives.
        complex_ = re.search(r'\b(not|never|unless|if|until|before|after|or|while)\b', text, re.I)
        action = 'unparsed'
        if not complex_:
            for name, pattern in [('pick_up', r'^pick\s+up\s+.+$'),
                                  ('place', r'^(?:put|place|store)\s+.+\s+(?:in|inside|into)\s+.+$'),
                                  ('close', r'^(?:close|shut)\s+.+$')]:
                if re.fullmatch(pattern, text, flags=re.I):
                    action = name
                    break
        target = re.sub(r'^(?:close|shut)\s+(?:the\s+|a\s+|an\s+)?', '', text, flags=re.I) if action == 'close' else object_concept
        criteria.append(tc.CriterionSpec(f'step_{i+1}', 'action', True, clause,
            'Explicit user task text; no reference outcome or added inventory/pose requirement',
            {'action': action, 'target': target, 'clause_index': i}))
    if not criteria:
        criteria.append(tc.CriterionSpec('step_1', 'action', True, description or 'Task not supplied',
            'No assessable task instruction supplied', {'action': 'unparsed'}))
    criteria.append(tc.CriterionSpec('completion', 'completion', True, 'All explicit subgoals',
        'Only explicit clauses; no claim that image-space checks certify full physical completion'))
    return tc.TaskCriteria('uploaded_task', description, destination or 'unspecified destination',
                           (tc.ObjectRequirement(object_concept),), tuple(criteria))


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def assess_action(spec, task, ev):
    import task_criteria as tc
    action = spec.params.get('action', 'unparsed')
    a = tc.CriterionAssessment(spec.criterion_id, 'action', spec.required, 'unverified', '')
    if action == 'unparsed':
        a.state = 'not_assessed'
        a.basis = 'Explicit instruction retained but not understood by the limited action parser. It is not silently counted as completed.'
        a.requirements.append(tc.EvidenceRequirement('task_specification', a.criterion_id,
            f'Clarify this explicit instruction as a checkable subgoal: {spec.description}'))
        return a
    if action == 'close':
        target = spec.params['target']
        a.basis = f'Closing {target} is an explicit subgoal. No independently validated articulation measurement establishes its final state. A frame-zero destination mask does not measure closure.'
        usable = []
        for p in ev.predicates:
            m = p.measurement
            if (p.kind != 'articulation_2d' or p.object_id != target or
                not tc._supports(ev, [p.evidence_id], p.kind, target, p.frame, p.value, p.view)):
                continue
            # All comparison geometry belongs to one stationary camera and the
            # same explicitly bound target. Motion/identity cannot come from IDs alone.
            start, lo, hi, before, after = (m.get(k) for k in
                ('start_frame', 'closed_threshold', 'open_threshold', 'start_open_fraction', 'end_open_fraction'))
            reference = m.get('reference_geometry_source')
            start_source = m.get('start_source_ref')
            # A calibration name must not alias the observation it is intended
            # to independently test. This guards direct URI aliases; semantic
            # calibration validity remains the trusted adapter's responsibility.
            if (not all(isinstance(s, str) and s.strip() for s in (reference, start_source, p.source_ref)) or
                unquote(reference.strip()) in {unquote(start_source.strip()), unquote(p.source_ref.strip())}):
                continue
            if (ev.camera_motion.get(p.view) != 'static' or not all(_number(v) for v in (start, lo, hi, before, after)) or
                not isinstance(start, int) or not 0 <= start < p.frame == ev.n_frames-1 or
                not 0 <= lo < hi <= 1 or not 0 <= before <= 1 or not 0 <= after <= 1 or before < hi or
                not m.get('reference_geometry_source') or not m.get('start_source_ref') or
                m.get('target_id') != target or m.get('view') != p.view or
                not any(view == p.view and left <= start < p.frame < right for view, left, right in ev.analyzed_ranges)):
                continue
            initial = next((s for s in ev.predicates if s.kind == 'articulation_2d' and s.object_id == target
                and s.view == p.view and s.frame == start and s.value == 'open'
                and s.source_ref == m['start_source_ref'] and s.measurement.get('open_fraction') == before
                and s.measurement.get('reference_geometry_source') == m['reference_geometry_source']
                and tc._supports(ev, [s.evidence_id], s.kind, target, start, 'open', p.view)), None)
            if initial is None:
                continue
            state = 'supported' if after <= lo else 'contradicted' if after >= hi else 'unverified'
            if p.value != {'supported': 'closed', 'contradicted': 'open', 'unverified': 'ambiguous'}[state]:
                continue
            usable.append((p, state, initial.evidence_id))
        views = {p.view for p, _, _ in usable}
        associated = target in ev.object_associations and ev.time_alignment_validated
        states = {s for _, s, _ in usable}
        if usable and len(states) == 1 and (len(views) == 1 or associated):
            a.state = next(iter(states))
            a.evidence_ids = tc._uniq(eid for p, _, start_id in usable for eid in (start_id, p.evidence_id))
            a.basis = (f'Independently sourced 2D target articulation at native final frame {ev.n_frames-1}: '
                       f'{"closed within the supplied image-space threshold" if a.state == "supported" else "still open within the supplied image-space threshold" if a.state == "contradicted" else "between the declared thresholds"}. '
                       'This does not measure latching, force, 3D geometry, placement or grasp/release.')
        elif usable:
            a.basis += ' Camera observations conflict or lack validated alignment/target association; no cross-camera vote is taken.'
            a.evidence_ids = tc._uniq(eid for p, _, start_id in usable for eid in (start_id, p.evidence_id))
        if a.state == 'unverified':
            a.requirements.append(tc.EvidenceRequirement('final_state_observation', a.criterion_id,
                f'Original before/after views of {target}, with independently checked open/closed geometry, the same target, camera-motion handling and a declared final-state scope. No inference is made from object disappearance.'))
        return a
    if action == 'pick_up':
        a.evidence_ids = list(ev.tracking_evidence_ids)
        a.basis = 'Object detections or motion near a gripper are context, not independent evidence that the specified object was grasped and lifted. No holding-sensitive or independently verified pickup event is supplied.'
        a.requirements.append(tc.EvidenceRequirement('gripper_measurement', a.criterion_id,
            'A time-aligned, object-associated holding/lift observation or holding-sensitive sensor measurement through pickup; jaw opening alone is insufficient.'))
    else:
        a.evidence_ids = list(ev.destination_evidence_ids)
        a.basis = 'A destination footprint and object boxes do not establish that the specified object was placed inside. No validated interior, associated placement event and task-final observation are supplied.'
        a.requirements.append(tc.EvidenceRequirement('destination_mask', a.criterion_id,
            'A validated destination interior and object-associated placement/final-position observations, separating overlap and occlusion from actual containment.'))
    for start, end in ev.tracking_missing_ranges:
        a.requirements.append(tc.EvidenceRequirement('continuous_tracking', a.criterion_id,
            f'Resolve missing observations at native frames {start}–{end-1}; do not bridge this gap with an invented trajectory.', frames=(start, end)))
    return a


def frame_ranges(frames):
    ranges = []
    for frame in sorted(set(frames)):
        if ranges and frame == ranges[-1][1]:
            ranges[-1][1] += 1
        else:
            ranges.append([frame, frame+1])
    return ranges


def camera_coverage(camera, observations):
    start, end = camera['frame_start'], camera['frame_end']
    for o in observations:
        if any(o.get(k, camera[k]) != camera[k] for k in ('camera_id','source_video_id')):
            raise ValueError('Observation camera/source provenance mismatch')
    observed = {o['frame_index'] for o in observations if o.get('frame_index') is not None and start <= o['frame_index'] < end}
    return {k: camera[k] for k in ('camera_id', 'source_video_id', 'crop', 'sha256', 'source_sha256', 'fps', 'n_frames', 'frame_start', 'frame_end')} | {
        'returned_observations': sum(o.get('frame_index') in observed for o in observations),
        'observed_ranges': frame_ranges(observed),
        'missing_ranges': frame_ranges(set(range(start, end))-observed),
        'outside_analysis': frame_ranges(set(range(camera['n_frames']))-set(range(start, end)))}


def select_context_frames(camera, observations, limit):
    """Bounded original context only; endpoints keep their existing reference order."""
    start, end = camera['frame_start'], camera['frame_end']
    picked = list(dict.fromkeys([start, end-1]))[:limit]
    coverage = camera_coverage(camera, observations)
    gaps = sorted(coverage['missing_ranges'], key=lambda r: r[1]-r[0], reverse=True)
    # Keep context around the longest gap, then fill the largest unsampled span.
    for left, right in gaps[:1]:
        candidates = [(left+right-1)//2] if limit-len(picked) == 1 else [left-1, right, (left+right-1)//2]
        for frame in candidates:
            if start <= frame < end and frame not in picked and len(picked) < limit:
                picked.append(frame)
    while len(picked) < min(limit, end-start):
        ordered=sorted(picked)
        left,right=max(zip(ordered,ordered[1:]), key=lambda pair: pair[1]-pair[0])
        frame=(left+right)//2
        if frame in picked: break
        picked.append(frame)
    return picked
