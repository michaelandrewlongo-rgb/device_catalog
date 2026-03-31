# ChoiceSpine NavLock - Navigation Instrument Platform

## What It Is

A set of navigated spine instruments designed to interface with Medtronic NavLock-compatible navigation systems (StealthStation). These are tracked surgical instruments with integrated reflective sphere arrays that allow real-time image-guided pedicle screw placement and spinal instrumentation. ChoiceSpine provides the implants and navigated instruments; the navigation platform itself is the Medtronic StealthStation.

## Components

- **NavLock-compatible navigated instruments** - awls, probes, taps, and screwdrivers with Medtronic NavLock tracker interfaces
- **NavLock tracker arrays** - reflective sphere arrays that snap onto the instrument handles via the NavLock coupling mechanism
- **Pedicle screw system** - ChoiceSpine's proprietary polyaxial and monoaxial pedicle screws, rods, and set screws (the implant side of the system)
- **Medtronic StealthStation** - the navigation console, camera, and patient reference frame (provided separately by the facility, not by ChoiceSpine)

The NavLock interface is a standardized mechanical coupling that allows third-party instruments to be tracked by the Medtronic StealthStation system. The tracker array attaches to the instrument and is recognized by the camera.

## Setup / Registration

### Pre-requisites
- A Medtronic StealthStation must be available in the OR with a current Spine software license.
- An intraoperative 3D imaging source (O-arm or 3D C-arm) must be available for automatic registration, or preoperative CT must be loaded for landmark-based registration.

### OR setup
1. Set up the StealthStation and camera per standard Medtronic spine navigation workflow.
2. Expose the spine. Attach the patient reference frame rigidly to a spinous process.
3. Acquire the intraoperative 3D spin (if using automatic registration) or perform surface/point registration to preoperative CT.

### Instrument preparation
1. Open the ChoiceSpine NavLock instrument tray on the sterile field.
2. Attach the NavLock tracker array to the first instrument you plan to use (awl or probe). The array snaps on and locks into a fixed, known geometry relative to the instrument tip.
3. On the StealthStation, select the corresponding instrument from the instrument library. The system must have the ChoiceSpine instrument definitions loaded (this is typically set up in advance by the Medtronic rep or the nav team).
4. Verify the instrument: place the tip in the reference frame divot, confirm accuracy on screen. The system should display the instrument tip position accurately on the 3D images.

### Navigation workflow
1. Navigate the awl to the pedicle entry point. Confirm trajectory on multiplanar views.
2. Create the pilot hole under navigation guidance.
3. Tap if needed (if a navigated tap is available, swap the tracker array to the tap).
4. Place the pedicle screw. If using a navigated screwdriver, attach the tracker array and confirm trajectory/depth in real time.
5. Swap the tracker array between instruments as needed during the case. Each swap requires verification in the divot.

## Workflow by Case Type

### Pedicle Screw Placement (Primary)
1. Standard navigation setup as above.
2. Navigate each pedicle with the tracked awl. Confirm entry point and trajectory.
3. Advance under real-time guidance. Monitor for cortical breach on axial and sagittal views.
4. Tap and place screws. Use the navigated screwdriver if available to confirm final position.

### Revision Surgery
1. Navigation is especially valuable when anatomy is distorted by prior fusion mass, hardware, or scar.
2. If prior hardware is in the field, expect metal artifact on the 3D spin. Navigate cautiously and correlate with anatomical landmarks.
3. The NavLock instruments function identically in revision cases; the challenge is image quality, not instrument compatibility.

### Percutaneous Screw Placement
1. Attach the reference frame to an exposed spinous process or use a percutaneous reference pin (per StealthStation spine workflow).
2. Navigate a tracked Jamshidi needle or awl to the pedicle percutaneously.
3. Confirm trajectory on navigation before advancing through the pedicle.

## Accuracy / Limitations

- **Instrument accuracy:** Dependent on the NavLock coupling precision and the StealthStation tracking system. Typical application accuracy is 1-2 mm when instruments are properly verified.
- **Verification threshold:** If the instrument tip does not match the divot position on screen within an acceptable margin (typically <2 mm), the instrument should not be used for navigation. Check for a loose tracker array or a bent instrument.
- **Tracker array rigidity is critical:** The NavLock coupling must be fully seated and locked. Any play between the tracker and the instrument handle introduces error.
- **Same limitations as StealthStation spine navigation apply:** accuracy degrades if the reference frame shifts, if the spine moves relative to the reference (e.g., during reduction maneuvers), or if the 3D spin has significant metal artifact.
- **Instrument library:** The StealthStation must have the ChoiceSpine NavLock instrument definitions pre-loaded. If the instruments are not in the library, they cannot be calibrated and used. Confirm this with the nav team before the case.

## Troubleshooting

| Problem | Fix |
|---|---|
| Instrument not recognized by StealthStation | Confirm the ChoiceSpine NavLock instrument definitions are loaded in the system. Contact the Medtronic or ChoiceSpine rep to load the instrument file. |
| Tracker array won't snap on securely | Inspect the NavLock coupling on both the array and the instrument handle for debris or damage. Clean and retry. If the coupling is worn, replace the array. |
| Instrument verification fails (tip not matching divot on screen) | Confirm tracker array is fully seated and locked. Check that the correct instrument is selected in the software. Try a different array. If the instrument is bent, discard it. |
| Accuracy seems off mid-case | Check reference frame stability. Re-verify the instrument in the divot. If error persists, re-acquire a 3D spin. |
| Tracker array spheres not detected | Clean spheres (blood, irrigation fluid). Confirm line of sight to camera. Replace damaged spheres. |

## Sizing/Specs

### Instrument Specifications
- **Interface standard:** Medtronic NavLock mechanical coupling (standardized third-party tracker interface)
- **Tracked instruments:** Awls, probes, taps, screwdrivers with NavLock coupling receptacles on handles
- **Tracker arrays:** Passive reflective sphere arrays (typically 4-sphere configuration); snap-lock attachment to instrument handles
- **Tracking type:** Optical infrared (passive reflective spheres tracked by StealthStation camera)
- **Application accuracy:** 1-2mm typical when instruments are properly verified (dependent on NavLock coupling precision and StealthStation tracking system)
- **Sterilization:** Instruments are reusable and autoclavable; single-use items per ChoiceSpine labeling must not be resterilized

### Pedicle Screw System
- ChoiceSpine proprietary polyaxial and monoaxial pedicle screws
- Rods and set screws (refer to ChoiceSpine technical documentation for specific screw diameter and length options)
- Standard titanium alloy construction

## Indications

- Image-guided (navigated) pedicle screw placement in thoracic and lumbar spine
- Open posterior spinal instrumentation with navigation assistance
- Percutaneous minimally invasive pedicle screw placement under navigation guidance
- Revision spine surgery where distorted anatomy (fusion mass, scar, hardware) makes freehand screw placement unreliable
- Any pedicle screw-based spine procedure where the surgeon elects to use Medtronic StealthStation navigation
- Degenerative, deformity, trauma, and tumor cases requiring pedicle screw fixation

## Compatible With

- **Navigation platform (required):** Medtronic StealthStation with current Spine software license
- **Intraoperative imaging:** Medtronic O-arm, Ziehm 3D C-arm, or any isocentric C-arm with 3D spin capability (for automatic registration); alternatively, preoperative CT with landmark-based registration
- **Patient reference frame:** Medtronic spinous process clamp or percutaneous reference pin (provided by the facility, not by ChoiceSpine)
- **NavLock tracker arrays:** Medtronic-standard NavLock passive reflective sphere arrays
- **Implants:** ChoiceSpine pedicle screws, rods, set screws (the navigated instruments are designed for ChoiceSpine's own implant system)
- **Instrument library requirement:** StealthStation must have ChoiceSpine NavLock instrument definitions pre-loaded; confirm with the Medtronic or ChoiceSpine representative before the case

## Use Notes

- The NavLock interface is a standardized mechanical coupling; any NavLock-compatible tracker array will physically attach, but the StealthStation must have the correct instrument definition file loaded to calibrate the geometry
- Tracker arrays are swapped between instruments during the case (awl to tap to screwdriver); each swap requires re-verification in the calibration divot
- Instrument accuracy is only as good as the NavLock coupling rigidity; any play between the tracker and handle introduces tracking error
- Navigation is a surgical adjunct, not a substitute for anatomical knowledge; always correlate navigated trajectory with clinical feel and anatomical landmarks
- The system does not include the StealthStation, camera, or patient reference frame; these are capital equipment provided by the facility
- For percutaneous cases, a percutaneous reference pin can replace the spinous process clamp
- In revision cases, expect metal artifact on the intraoperative 3D spin; navigate cautiously and correlate with anatomy
- Confirm line of sight between the camera and both the reference frame and the instrument tracker arrays throughout the procedure
- If the reference frame is bumped or the patient is repositioned, navigation must be re-registered

## Key Differences vs Competitors

| Feature | ChoiceSpine NavLock | Medtronic StealthStation (native instruments) | Stryker SpineMap 3D | Globus ExcelsiusGPS | Brainlab Cirq |
|---|---|---|---|---|---|
| **Type** | Navigated instruments (third-party) | Navigated instruments (OEM) | Navigated instruments (OEM) | Robotic guidance | Robotic guidance |
| **Navigation platform** | Medtronic StealthStation (required) | Medtronic StealthStation | Stryker navigation console | Globus proprietary system | Brainlab navigation |
| **Instrument tracking** | NavLock passive optical | NavLock passive optical | Passive optical | Robotic arm + optical | Robotic arm + optical |
| **Implant system** | ChoiceSpine proprietary | Medtronic (CD Horizon, Solera, etc.) | Stryker (Xia, Serrato, etc.) | Globus (Revere, Creo, etc.) | Compatible with multiple |
| **Key advantage** | Third-party flexibility; use StealthStation with non-Medtronic implants | Full integration, widest install base | SpineMask auto-labeling, integrated workflow | Robotic arm guidance, reduced radiation | Compact robotic arm, open platform |
| **Key limitation** | Requires pre-loaded instrument definitions; no robot option | Locked to Medtronic implants | Locked to Stryker implants | Separate capital purchase, learning curve | Separate capital purchase |

- ChoiceSpine NavLock fills a niche: surgeons who prefer the Medtronic StealthStation for navigation but want to use a non-Medtronic pedicle screw system
- Unlike OEM navigated instruments, third-party NavLock instruments require the facility to pre-load instrument definitions, which adds a setup step
- Robotic systems (ExcelsiusGPS, Mazor X, Cirq) offer guided trajectories via a robotic arm, a fundamentally different approach from handheld navigated instruments
- All navigated/robotic systems share the same core limitation: accuracy depends on rigid reference frame fixation and valid registration

## Contraindications / Warnings

- The NavLock instruments are designed exclusively for use with Medtronic NavLock-compatible navigation systems. Do not attempt to use them with other navigation platforms.
- Always verify instrument accuracy in the divot before navigating. Do not navigate with an unverified instrument.
- The tracker array must be rigidly coupled to the instrument. Do not use an instrument if the array feels loose or rotates on the handle.
- Navigation is a surgical adjunct. The surgeon must independently confirm screw position by clinical feel, anatomical landmarks, and/or postoperative imaging.
- If the reference frame is bumped, loosened, or if the patient is repositioned, navigation is invalid. Re-register.
- Single-use items must not be reused or resterilized per ChoiceSpine labeling.

## Sizing/Specs

### Instrument Specifications
- **Tracker interface:** Medtronic NavLock mechanical coupling (standardized snap-on connection)
- **Tracker arrays:** Passive reflective sphere arrays (typically 4 spheres in a fixed geometry)
- **Tracked instruments:** Awls, probes, taps, screwdrivers (instrument-specific tip geometries defined in the StealthStation software library)
- **Tracking technology:** Optical infrared (passive reflective), dependent on Medtronic StealthStation camera
- **Application accuracy:** 1-2 mm typical (dependent on NavLock coupling precision, StealthStation calibration, and registration method)

### System Requirements
- Medtronic StealthStation navigation console with current Spine software license
- ChoiceSpine NavLock instrument definitions loaded in the StealthStation instrument library
- Intraoperative 3D imaging source (O-arm or 3D C-arm) for automatic registration, or preoperative CT for landmark-based registration
- Patient reference frame (spinous process clamp, tracked by the camera)

### Implant System
- ChoiceSpine polyaxial and monoaxial pedicle screws, rods, and set screws (separate from the navigation instruments)
- Refer to ChoiceSpine catalog for specific screw diameter and length options

## Indications

- Image-guided pedicle screw placement in thoracic and lumbar spine (open, mini-open, or percutaneous)
- Revision spine surgery where anatomy is distorted by prior fusion mass, hardware, or scar tissue
- Deformity correction surgery requiring navigated instrumentation
- Any spinal instrumentation procedure where real-time image guidance is desired and a Medtronic StealthStation is available
- Not indicated as a standalone navigation system; requires Medtronic StealthStation platform

## Compatible With

- **Navigation platform:** Medtronic StealthStation (NavLock-compatible models)
- **Imaging:** Medtronic O-arm, 3D-capable C-arms (for automatic registration), or preoperative CT (for landmark-based registration)
- **Implants:** ChoiceSpine pedicle screw systems (polyaxial, monoaxial); the navigated instruments guide screw placement but are not implant-specific
- **Patient reference frames:** Standard Medtronic spinous process clamps or percutaneous reference pins
- **Sterilization:** Instruments and tracker arrays are reusable and reprocessed per ChoiceSpine IFU

## Use Notes

- The NavLock interface is an open standard that allows third-party instrument manufacturers (like ChoiceSpine) to create tracked instruments compatible with the Medtronic StealthStation ecosystem. This gives surgeons implant choice while using a familiar navigation platform.
- The tracker array must be swapped between instruments during a case (e.g., from awl to tap to screwdriver). Each swap requires re-verification in the calibration divot.
- Instrument definitions must be pre-loaded on the StealthStation before the case. Confirm with the Medtronic rep or navigation team during pre-case planning. If the definitions are missing, the instruments cannot be calibrated.
- Accuracy is equivalent to Medtronic's own NavLock instruments when properly calibrated. The mechanical coupling is standardized.
- The primary advantage over Medtronic's own navigated instruments is access to ChoiceSpine's implant system while maintaining navigation compatibility.
- All standard StealthStation spine navigation limitations apply: reference frame stability, line-of-sight requirements, accuracy degradation with patient movement.

## Key Differences vs Competitors

| Feature | ChoiceSpine NavLock | Medtronic StealthStation Native Instruments | Stryker SpineMap 3D | Globus ExcelsiusGPS |
|---|---|---|---|---|
| Navigation platform | Medtronic StealthStation (dependent) | Medtronic StealthStation | Stryker proprietary | Globus proprietary |
| Tracking method | Optical (passive reflective, NavLock coupling) | Optical (passive reflective, NavLock coupling) | Optical (passive reflective) | Robotic arm + optical |
| Instrument ecosystem | ChoiceSpine implants only | Medtronic implants | Stryker implants | Globus implants |
| Standalone capability | No (requires StealthStation) | No (requires StealthStation) | Yes (integrated system) | Yes (integrated robotic system) |
| Robotic guidance | No | No (unless paired with Mazor X) | No | Yes (robotic arm positions guide tube) |
| Cost model | Lower implant cost with existing StealthStation | Bundled with StealthStation | Requires Stryker nav system | Requires ExcelsiusGPS robot |

- ChoiceSpine NavLock is a value proposition: it lets surgeons use a less expensive implant system while leveraging an existing Medtronic StealthStation installation.
- Unlike Stryker or Globus systems, ChoiceSpine does not provide its own navigation platform. It is entirely dependent on Medtronic infrastructure.
- The NavLock standard is Medtronic-proprietary. ChoiceSpine instruments are not compatible with Stryker, Globus, or Brainlab navigation systems.
- Compared to robotic systems (Mazor X, ExcelsiusGPS), NavLock navigation provides real-time guidance but not robotic arm positioning of instruments.

## Also Known As

- ChoiceSpine NavLock
- NavLock Navigation Instruments
- ChoiceSpine Navigated Pedicle Screw System
- NavLock-compatible instruments
