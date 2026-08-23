# Medtronic StealthStation S8 - Cranial Navigation

## What It Is

Optical frameless stereotactic navigation system. An infrared camera tracks reflective spheres on instruments and a patient reference to display real-time instrument position on preoperative imaging (CT, MRI, or merged datasets). Used for tumor resection, biopsy, shunt placement, and any cranial procedure requiring image guidance.

## Components

**Capital equipment:**
- StealthStation S8 console (touchscreen workstation on wheeled cart)
- Infrared camera array with laser aiming system
- Footswitch (wireless or wired)

**Reusable instruments:**
- Cranial Reference (patient tracker, 961-337) - attaches to Vertek arm, defines patient position
- Vertek II Articulating Arm (9734252) - multi-pivot arm, mounts to Mayfield via Short Bedrail Adapter
- Dual Starburst (960-535) - provides two Vertek arm attachment points (needed for biopsy with Vertek Passive Biopsy Kit)
- Passive Planar Registration Probe (960-556) - standard pointer for registration and navigation
- Scope Probe (9730269) - bayonet-style, for use under the microscope
- Navigus Probe (9733157) - used with Trajectory Guide Kit for biopsy aiming
- Vertek Probe (9733158) - used with Vertek Passive Biopsy Kit for biopsy aiming
- Precision Aiming Device (960-539) - two-axis pivot for biopsy needle guidance

**Single-use / sterile items:**
- Sterile Spheres (9730950, 5-pack 9730951) - snap onto instrument/reference posts
- Touch-n-Go Pointer (9731965) - for fiducial-based registration
- PCI Handle (9730092) + PCI Tip (9731116) - Passive Catheter Introducer for shunt/catheter placement
- Biopsy Needle Kit (9733068) - side-cutting needle with depth markings at 10 mm intervals
- Biopsy Needle Stop - limits depth of advancement
- Stop Adjustment Tool - metric ruler for setting the needle stop
- Aspirator Tube - connects to syringe for biopsy suction
- Trajectory Guide Kit (External 9733065, Internal 9733066) - base, guide stem, adapters (1.9/2.2/2.6 mm), locking ring, screwdriver
- Reducing Tubes (1.9 mm, 2.2 mm, 2.6 mm) - for Vertek Passive Biopsy Kit

**Software features:**
- StealthMerge - co-registers multiple imaging datasets (CT + MRI, MRI + fMRI, MRI + PET)
- Tracer registration, Touch-n-Go registration, PointMerge registration
- Surgical planning (entry/target points, trajectory simulation)
- Guidance view (bull's-eye display for trajectory alignment)
- Look Ahead view (probe's-eye at tip, +5 mm, +10 mm, +15 mm)
- Tip projection (virtual extension beyond instrument tip)
- Accuracy checkpoints (intraoperative drift monitoring)

## Setup / Registration

### Pre-op imaging
1. Transfer DICOM images to StealthStation via hospital network (DICOM push from PACS). Confirm slice count and contiguity on import. The system rejects scans with gantry tilt, missing slices, or insufficient image count.
2. Select Surgeon, then Select Patient. Choose the correct exam.

### Equipment setup
1. Power on the StealthStation. System runs through the Set Up Equipment task showing connected devices.
2. Connect the camera cable to the console. Confirm green status on screen.
3. Attach the Vertek Articulating Arm to the Mayfield Skull Clamp via the Short Bedrail Adapter.
4. Attach the Cranial Reference (961-337) to the Vertek arm. Position it as close to the surgical field as possible without impeding access. The system warns if a touched landmark is >30 cm from the reference center.
5. Lock the Vertek arm securely. If it slips after registration, you must re-register.

### Instrument verification
1. Snap sterile spheres onto all instruments and the patient reference.
2. Insert each instrument tip into the divot on the patient reference, perpendicular to the surface.
3. Confirm both instrument and reference are in the camera's Tracking View.
4. Hold steady 2 seconds or press footswitch. Listen for chime (verified) vs. bonk (failed).
5. Repeat for each instrument.

### Camera positioning
1. Clear line of sight between camera lenses and sterile spheres.
2. Position the camera approximately 1.75 m (6 ft) from the patient reference.
3. Use the laser trigger on the camera handle to aim. Center the laser on the patient reference.
4. Open the Tracking View. Adjust camera aim so spheres appear centered. Adjust distance until the distance indicator bar is near mid-range.

### Registration (choose one method)

**Tracer Registration (most common, no fiducials needed):**
1. Touch the registration pointer to landmark 1 (tip of nose or most anterior point in the scan). Hold steady until verification sound.
2. Touch landmark 2 (center of forehead). Hold steady.
3. Touch landmark 3 (3 cm to the patient's left of landmark 2). Hold steady.
4. Place pointer tip on the patient's nose, press and hold footswitch. Trace around bony landmarks: nose, brow, mastoids, scalp. Cover as many uniquely-shaped areas as possible. Maintain skin contact. If you need to lift the pointer, release the footswitch first.
5. Continue until Tracing Progress reaches 100%. The software auto-matches and advances to accuracy verification.

**Touch-n-Go Registration (requires pre-placed adhesive fiducials):**
1. Apply fiducials to the scalp before imaging. Mark them on the scan.
2. In the Register task, click [Touch-n-Go]. Confirm the Touch-n-Go Pointer is selected.
3. Touch the pointer tip to the center of each fiducial for 2 seconds. Touch at least 4 fiducials. Predicted maximum error must be <5.0 mm.

**PointMerge Registration (landmark-based, no fiducials):**
1. Click [Register with PointMerge].
2. Click identifiable landmarks on the 3D skin model (e.g., nasion, lateral canthi, tragus). Click [Store] for each. Use 7-8 well-distributed landmarks (minimum 4).
3. Touch each stored landmark on the patient with the registration probe. Landmarks turn green (accurate), yellow (marginal), or red (excluded).
4. Predicted error must be <5.0 mm. After 4th landmark, the system displays a Sphere of Accuracy: green circle = estimated error <=1 mm; yellow circle = <=2 mm. Confirm the surgical target lies within these circles.

### Verify accuracy
1. Touch the probe to identifiable bony landmarks (e.g., nasion, EAC, inion).
2. Compare the on-screen crosshair position to the known anatomy in all three orthogonal views.
3. Check at least 3 points. If accuracy is unacceptable, re-register.

### Sterile transition
1. Remove the non-sterile patient reference. Note the Medtronic logo orientation.
2. Drape the patient.
3. Attach the sterile patient reference to the Vertek arm swivel mount. Match alignment post to alignment notch. Puncture drape with mounting screw. Tighten securely.

## Workflow by Case Type

### Tumor Resection / Open Craniotomy
1. Register using Tracer (typical) or PointMerge.
2. Use StealthMerge if navigating on multiple modalities (e.g., CT for bone, MRI for tumor, fMRI for eloquent cortex). Merge exams, verify alignment with Blend/Split-window.
3. Plan: set entry and target if desired, but often used freehand.
4. Navigate with the Passive Planar Registration Probe or Scope Probe (under microscope). Use the standard 4-quadrant view (axial, coronal, sagittal, 3D model).
5. Create Accuracy Checkpoints early: click [Control Panel] > [Create Checkpoints]. Touch 4 identifiable points on exposed bone/dura. Monitor Distance to Checkpoint during the case; >2 mm suggests drift. Use [Realign Registration] if needed.
6. Green crosshairs = active tracking; red crosshairs = tracking lost (check line of sight).

### Shunt Placement
1. Register as above.
2. Define a surgical plan: set Target (e.g., ipsilateral frontal horn) and Entry (e.g., Kocher's point). Use [Set Target] and [Set Entry].
3. Use the Guidance view (bull's-eye): small orange circle = target, large green circle = aiming area around the PCI tip. Align center of green circle with target.
4. Set up Trajectory 1 and Trajectory 2 views plus Probe's Eye view.
5. Insert the sterile PCI stylet through the sterile catheter. Place PCI tip at the entry point.
6. Advance along the plan, keeping the target dot centered in the aiming circle.

### Stereotactic Biopsy

**Option A: Trajectory Guide Kit (skull-mounted)**
1. Define surgical plan (entry + target).
2. Mark entry point on scalp. Select base type: standard (10 deg range from vertical with 14 mm burr hole) or angled (5-25 deg depending on direction).
3. Make incision, strip periosteum, create 14 mm burr hole.
4. Anchor base to skull with three titanium screws (1.6 mm x 8 mm). Tighten evenly.
5. Snap guide stem into base, thread locking ring. Loosen locking ring.
6. Insert Navigus Probe into guide stem. Aim using Guidance view and trajectory views.
7. Tighten locking ring. Press footswitch or click [Lock Trajectory].
8. Remove Navigus Probe. Insert 2.2 mm adapter into guide stem.
9. The system reports the Tip Stop Point = adapter length (50 mm) + plan length. To center the cutting window on the target, add 7 mm to the Tip Stop Point (cutting window starts 3 mm from needle tip, is 8 mm long).
10. Set the depth stop on the biopsy needle using the Stop Adjustment Tool.
11. Advance needle through adapter until depth stop contacts adapter top.
12. Open cutting window (align notches), draw suction, close window (rotate 180 deg). Confirm window is closed before retracting.

**Option B: Vertek Passive Biopsy Kit (arm-mounted)**
1. Connect Vertek Arm to Dual Starburst (starburst must be on Mayfield before arm is attached). Attach precision aiming device to arm's instrument swivel mount.
2. Position arm above entry point. Lock arm.
3. Make incision, burr hole.
4. Remove arm (with precision aiming device still attached), set aside in sterile field.
5. Re-attach arm to Dual Starburst, secure with base attachment screw.
6. Aim with Vertek Probe in precision aiming device using Guidance view. Lock trajectory.
7. Remove Vertek Probe, insert 2.2 mm reducing tube.
8. Tip Stop Point = reducing tube length (70 mm) + plan length.
9. Same biopsy needle technique as above.

**Critical biopsy safety notes:**
- Always use the 2.2 mm adapter/reducing tube with the passive biopsy needle.
- Visually confirm the cutting window is closed before advancing or retracting the needle through the adapter. Moving the needle with the window open causes unnecessary tissue trauma.
- Do not remove the guide assembly until a satisfactory sample is confirmed.

## Accuracy / Limitations

- **Registration accuracy:** Tracer registration is typically 1-2 mm surface accuracy. PointMerge displays a Sphere of Accuracy: green zone <=1 mm, yellow zone <=2 mm. Touch-n-Go with well-placed fiducials can achieve <2 mm. System blocks navigation if predicted error exceeds 5.0 mm.
- **Instrument verification threshold:** Distance to divot must be <2.0 mm. Geometry error must be <0.5 mm, otherwise replace the instrument.
- **Brain shift:** The system navigates on preoperative images. After dural opening, CSF drainage, tumor debulking, or gravity-dependent retraction, cortical and subcortical anatomy shifts. Navigation accuracy degrades progressively. This is the primary limitation for deep targets during open craniotomy.
- **Accuracy checkpoints:** Distance to Checkpoint >2 mm indicates potential reference shift. If inaccuracy persists, re-register using checkpoints as landmarks via [Realign Registration].
- **Landmark placement >30 cm from reference center:** System warns; accuracy degrades at distance.
- **Sterile reference orientation:** Must match the original logo orientation when re-attaching post-drape. Incorrect orientation invalidates registration.

## Troubleshooting

| Problem | Fix |
|---|---|
| DICOM import: slices missing | Delete exam via [Admin] > Patients tab. Have radiology re-push. Watch slice counter in upper left. |
| Error: "does not contain valid data for navigation" | Check scanner settings. Re-import. If persistent, call Medtronic support. |
| Error: "gantry tilt" | Re-scan without gantry tilt. |
| Error: "does not contain contiguous slices" | Have radiology reformat per Imaging Protocol (9732379). |
| Warning: "non-axial scan" | Click [Modify Images] > [Reorient] to correct orientation. |
| Camera connection fails at Set Up Equipment | Power off. Check cable crimps, connector pins. Confirm cable seated at both ends. Power on. |
| Instrument verification fails (bonk) | Confirm tip is in the divot bottom, perpendicular. Check distance to divot (<2.0 mm). Check geometry error via [Camera] > [Camera Details] (<0.5 mm). If >0.5 mm, use a different instrument. |
| Instrument verification fails / red status | Rotate spheres to confirm secure seating. Check for sphere damage or contamination (blood, fluid). Wipe spheres clean. Ensure camera has line of sight. Cover reflective surfaces. Turn off or redirect OR lights. Remove drape wrinkles over reference spheres. |
| Tracer registration fails | Re-start tracing. Ensure you are tracing bony landmarks included in the scan FOV. Do not trace soft tissue not in the scan. |
| Accuracy poor after registration | Re-register. Try a different method (switch from Tracer to PointMerge or vice versa). Confirm no reference frame shift. |
| Crosshairs turn red during navigation | Line of sight blocked. Clear obstructions between camera and spheres. Move camera closer if needed. |
| Accuracy degrades mid-case | Check accuracy checkpoints (Distance to Checkpoint >2 mm = drift). Re-register using [Realign Registration] with stored checkpoints. Consider brain shift if working after CSF loss or debulking. |
| Need to move exam between patients | [Admin] > Patients tab > select exam > [Move Selected Exams] > choose or create patient. |

## Contraindications / Warnings

- Navigation is an adjunct, not a substitute for surgical judgment. The surgeon must independently verify anatomical accuracy at all times.
- Do not bump or reposition the patient reference after registration. Any movement invalidates registration. If the Vertek arm slips, re-register.
- The laser positioning system emits laser radiation. Never aim at eyes.
- Physically inspect all instruments before use. Never use a bent or damaged instrument.
- Do not use the same SureTrak II array on two different instruments. Do not use SureTrak II on flexible instruments.
- Single-use items (sterile spheres, PCI tip, biopsy needle kit, trajectory guide kit) must not be reused or resterilized.
- The system navigates on preoperative images only. It does not account for intraoperative brain shift, edema, or tissue deformation.
- Always confirm cutting window is closed before advancing or retracting the biopsy needle through the adapter.
- Do not over-tighten trajectory guide base screws on curved skull surfaces (risk of cracking the base).
- If accuracy checkpoints are not established and the reference shifts intraoperatively, you must re-register or abandon navigation.

## Also Known As

- StealthStation S8
- StealthStation Cranial
- Stealth Navigation
- Medtronic Cranial Nav
- "Stealth" (common OR shorthand)
- Synergy Cranial (older software generation)
