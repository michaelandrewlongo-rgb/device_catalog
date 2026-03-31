# Mazor X Stealth Edition (Medtronic)

**Manufacturer:** Medtronic (originally Mazor Robotics, acquired by Medtronic 2018)
**Category:** Navigation / Robotic Guidance (Capital Equipment)

## What It Is

The Mazor X Stealth Edition is a robotic guidance platform for spine surgery that integrates a robotic arm with the Medtronic StealthStation navigation system and O-arm intraoperative imaging. The system uses preoperative CT-based 3D planning software to allow the surgeon to plan pedicle screw trajectories, screw sizes, and entry points before surgery. Intraoperatively, the robotic arm positions a rigid guide tube along the planned trajectory, and the surgeon drills and inserts screws through the tube. The StealthStation provides real-time navigation feedback during the procedure. It is capital equipment, not an implant. The system supports both open and percutaneous (MIS) pedicle screw placement.

## Sizing/Specs

### System Components
- **Robotic arm:** Compact robotic arm mounted to the operating table via a bed-rail clamp; positions a rigid guide tube along planned screw trajectories
- **Planning workstation:** Preoperative 3D planning software for screw trajectory, diameter, and length planning on CT images
- **Navigation integration:** Full integration with Medtronic StealthStation (optical infrared tracking)
- **Imaging integration:** Medtronic O-arm (for intraoperative registration and verification)
- **Guide tubes:** Rigid cylindrical guide tubes through which the surgeon drills and inserts screws; various inner diameters to match drill and screw sizes
- **Tracking:** Optical infrared passive reflective arrays on the robotic arm and patient reference frame

### Technical Specifications
- **Degrees of freedom:** Refer to Medtronic technical documentation for exact robotic arm specifications
- **Accuracy:** Published studies report screw placement accuracy of 97-99% (Gertzbein-Robbins Grade A or B)
- **Planning capability:** Accepts preoperative CT (DICOM); surgeon plans all screw trajectories preoperatively
- **Registration:** Intraoperative O-arm scan merged with preoperative CT plan for automatic registration
- **Workflow modes:** Guided (robotic arm positions guide tube) or navigated (StealthStation navigation without robotic arm)

### Space Requirements
- Requires dedicated OR space for the robotic arm, StealthStation console, and O-arm
- The robotic arm clamps to the bed rail on the side of the approach

## Indications

- Robotic-guided pedicle screw placement in open or percutaneous (MIS) spine surgery
- Degenerative spine disease requiring instrumented fusion (lumbar, thoracic, cervical)
- Adult spinal deformity correction (scoliosis, kyphosis) requiring long-segment instrumentation
- Spinal trauma requiring pedicle screw fixation
- Revision spine surgery with distorted anatomy
- Tumor or infection cases requiring instrumented stabilization
- Any pedicle screw-based procedure where improved accuracy, reproducibility, or reduced surgeon radiation exposure is desired

## Contraindications

- Patient anatomy or body habitus that prevents O-arm imaging or robotic arm positioning
- Procedures where the robotic arm cannot be securely clamped to the operating table
- OR environments without adequate space for the full system (robotic arm, O-arm, StealthStation)
- The system is a guidance adjunct; it does not replace surgical judgment. Surgeon must independently verify screw position.
- Not indicated for procedures that do not involve pedicle screw or similar guided instrument placement
- Standard contraindications for ionizing radiation apply (O-arm imaging)

## Compatible With

- **Navigation platform:** Medtronic StealthStation (required; the Stealth Edition is the StealthStation-integrated version of Mazor X)
- **Imaging:** Medtronic O-arm O2 (required for intraoperative registration and verification)
- **Implant systems:** Compatible with Medtronic spine implant systems; can also be used with non-Medtronic screws if the guide tube inner diameter accommodates the drill and screw dimensions
- **Planning software:** Integrated preoperative planning module (accepts standard DICOM CT)
- **Operating tables:** Requires a radiolucent table with bed rails that accept the robotic arm clamp

## Use Notes

- **Preoperative planning:** The surgeon plans all screw trajectories on the preoperative CT using the Mazor planning software. This is done before the day of surgery or in the OR before the case starts. The plan specifies entry point, trajectory angle, screw diameter, and screw length for each level.
- **Intraoperative workflow:** (1) Position patient, attach reference frame. (2) Clamp robotic arm to bed rail. (3) Acquire O-arm 3D scan. (4) System merges the intraoperative scan with the preoperative CT plan (automatic registration). (5) Surgeon selects a planned screw on the display. (6) Robotic arm moves to position the guide tube along the planned trajectory. (7) Surgeon drills through the guide tube, taps if needed, and inserts the screw. (8) Repeat for each screw. (9) Optional verification O-arm scan.
- **Open vs. percutaneous:** For open cases, the robotic arm positions the guide tube over the exposed anatomy. For percutaneous MIS cases, the guide tube is positioned over the skin, and the surgeon makes a stab incision through which the Jamshidi needle or drill is advanced through the guide tube.
- **Accuracy advantage:** The robotic arm holds a rigid trajectory that does not drift, unlike a surgeon's hand. This is particularly beneficial for percutaneous cases where tactile feedback from bony anatomy is absent.
- **Radiation reduction:** The surgeon does not need to hold instruments under fluoroscopy during screw placement. The robotic arm holds the trajectory. This reduces surgeon hand radiation exposure.
- **Failure modes:** If the reference frame shifts, the registration is invalid and the robotic arm will guide to incorrect trajectories. Re-registration (new O-arm scan) is required. If the robotic arm cannot reach a planned trajectory (e.g., due to soft tissue or retractor interference), the surgeon can fall back to standard StealthStation navigation without the robotic arm.
- **Learning curve:** The system requires dedicated training. Initial cases are slower than freehand or standard navigation as the team learns the workflow. Efficiency improves with experience.
- **Capital cost:** Significant investment. Requires the Mazor X robotic arm, StealthStation, and O-arm. Facilities typically justify the cost through volume and potential reduction in revision surgery for malpositioned screws.

## Key Differences vs Competitors

| Feature | Medtronic Mazor X Stealth | Globus ExcelsiusGPS | Brainlab Cirq | Stryker SpineMap 3D (no robot) |
|---|---|---|---|---|
| Robotic arm | Yes (bed-mounted) | Yes (floor-mounted) | Yes (microscope-style arm) | No |
| Navigation integration | Medtronic StealthStation | Globus proprietary | Brainlab proprietary | Stryker proprietary |
| Imaging | O-arm (required) | Compatible with multiple 3D C-arms | Compatible with multiple 3D C-arms | Compatible with O-arm and 3D C-arms |
| Preoperative planning | Yes (CT-based 3D planning) | Yes (CT-based 3D planning) | Limited (primarily intraoperative) | No preop planning module |
| MIS/percutaneous | Yes (primary use case) | Yes | Yes | Yes (navigated, not robotic) |
| Mounting | Bed rail clamp | Floor-mounted (larger footprint) | Attached to microscope stand or table | N/A |
| Implant ecosystem | Medtronic (primarily) | Globus (primarily) | Implant-agnostic | Stryker |
| Vertebral auto-labeling | No | No | No | Yes (SpineMask) |

- Mazor X Stealth and ExcelsiusGPS are the two dominant robotic spine platforms. Mazor X advantages: deep integration with StealthStation and O-arm, bed-mounted arm (smaller floor footprint), robust preoperative planning software. ExcelsiusGPS advantages: floor-mounted arm (does not move with bed adjustments), built-in navigation (no separate nav system needed).
- Brainlab Cirq is a lighter-weight robotic arm with less rigid guidance than Mazor X or ExcelsiusGPS. It is more portable and less expensive but provides less robust trajectory holding.
- SpineMap 3D (Stryker) provides navigation without robotics. It has SpineMask auto-labeling, which neither Mazor X nor ExcelsiusGPS offers. However, it lacks the robotic arm guidance that reduces variability in screw placement.
- All robotic systems share common limitations: capital cost, OR setup time, learning curve, and dependence on reference frame stability. None eliminate the need for surgical judgment.

## Also Known As

- Mazor X
- Mazor X Stealth Edition
- Mazor X Stealth
- Medtronic Mazor
- Mazor Robotics (legacy company name)
- Renaissance (predecessor system, now obsolete)
- Spine robot (informal)
- Mazor robotic system
