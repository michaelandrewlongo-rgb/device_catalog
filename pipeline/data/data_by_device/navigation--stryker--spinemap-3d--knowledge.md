# Stryker SpineMap 3D / SpineMask - Intraoperative Spinal Navigation

## What It Is

Software-based 3D spinal navigation platform that runs on Stryker's surgical navigation system. Uses intraoperative 3D fluoroscopic or O-arm imaging to generate a navigable 3D volume of the spine. SpineMask is the integrated vertebral segmentation and auto-labeling feature that identifies individual vertebral levels in the acquired 3D dataset. Designed for pedicle screw placement, interbody procedures, decompression, and other instrumented spine surgery requiring real-time image guidance.

## Components

- **Stryker Navigation System** - console with display and tracking camera (optical infrared tracking)
- **SpineMap 3D software** - 3D navigation application loaded on the Stryker navigation platform
- **SpineMask module** - automated vertebral body segmentation and level identification within SpineMap 3D
- **Intraoperative 3D imaging source** - typically an O-arm or isocentric C-arm with 3D spin capability, providing the volumetric dataset
- **Patient reference frame** - spinous process clamp or other rigid fixation to the exposed spine, tracked by the camera
- **Navigated instruments** - tracked probes, awls, tap, screwdriver, with reflective sphere arrays

## Setup / Registration

### Pre-op planning
1. Standard preoperative CT or MRI for surgical planning. SpineMap 3D navigates on the intraoperative 3D spin, not preoperative images, so no DICOM transfer to the nav system is required in the standard workflow.

### OR setup
1. Position the navigation camera with clear line of sight to the operative field. Typical placement is at the head or foot of the bed, depending on the levels being instrumented.
2. Power on the Stryker navigation system. Launch SpineMap 3D.
3. Perform the surgical approach (midline or percutaneous). Attach the patient reference frame rigidly to a spinous process or iliac crest. This must remain absolutely fixed throughout the navigated portion of the case.

### Intraoperative 3D acquisition
1. Position the O-arm or 3D C-arm around the patient, centered on the target levels.
2. Acquire a 3D spin. The dataset transfers automatically to the SpineMap 3D system.
3. SpineMask processes the volume: it segments individual vertebral bodies and automatically assigns level labels. The surgeon verifies and corrects any mislabeled levels on the touchscreen.

### Registration
- Registration is automatic with intraoperative imaging. Because the 3D spin is acquired with the reference frame already attached and in the camera's field of view, the spatial relationship between the images and the patient is established at the time of acquisition. No separate point-matching or surface-tracing step is needed.
- Verify accuracy by touching a known anatomical landmark with the navigated probe and confirming correspondence on the 3D images.

### Instrument calibration
1. Verify each navigated instrument by placing its tip in the calibration divot on the reference frame (or a dedicated verification jig).
2. Confirm accuracy on screen before proceeding.

## Workflow by Case Type

### Pedicle Screw Placement (Open or Percutaneous)
1. Acquire intraoperative 3D spin with reference frame attached.
2. SpineMask identifies vertebral levels. Confirm labeling.
3. Navigate the awl or probe to the planned pedicle entry point. Use multiplanar views (axial, sagittal, coronal) to confirm trajectory through the pedicle into the vertebral body.
4. Monitor trajectory in real time. Confirm the instrument stays within the pedicle cortex.
5. Tap if needed, then place the screw. If using a navigated screwdriver, confirm final screw position on the display.
6. Repeat for each level. If the reference frame is bumped or the patient is repositioned, re-acquire a 3D spin.

### Interbody Fusion (TLIF/PLIF/ALIF)
1. Navigate for pedicle screw placement as above.
2. Use navigation to confirm the disc space entry point and trajectory for the interbody cage.
3. Navigate the cage insertion if using a tracked insertion instrument.

### Decompression
1. Navigate to confirm the target levels and laterality.
2. Use the navigated probe to identify lamina borders, facet joints, and the extent of required decompression.

### Multi-level or Deformity Cases
1. SpineMask is particularly useful here for positive level identification across long constructs.
2. Acquire the 3D spin covering the maximum number of levels in a single acquisition. If the construct exceeds the field of view, a second spin centered on the remaining levels may be needed, with re-registration to a new or repositioned reference frame.

## Accuracy / Limitations

- **Registration accuracy:** Because registration is based on intraoperative imaging acquired with the reference frame in situ, there is no fiducial error or surface-matching error. Accuracy is typically 1-2 mm at the time of acquisition, limited by the spatial resolution of the 3D spin.
- **No brain shift equivalent, but:** Accuracy degrades if the spine moves relative to the reference frame. Muscle retraction, reduction maneuvers, or patient repositioning can shift vertebral segments relative to the reference. Any manipulation that could move the spine relative to the reference requires re-acquisition.
- **SpineMask auto-labeling:** Reliable for normal and moderately degenerated anatomy. May mislabel in severe deformity, transitional anatomy, or prior fusion with hardware artifact. Always verify labels manually.
- **Metal artifact:** Prior hardware in the field of view can degrade 3D image quality and interfere with segmentation.
- **Field of view:** Single 3D acquisition covers a limited number of levels (typically 6-8 depending on the imaging system). Long constructs may require multiple acquisitions.
- **Radiation:** Each 3D spin delivers a radiation dose roughly equivalent to a limited CT scan. Minimize re-spins when possible.

## Troubleshooting

| Problem | Fix |
|---|---|
| SpineMask mislabels vertebral levels | Manually correct on the touchscreen before proceeding. Count from the sacrum up or from a known landmark (e.g., rib-bearing vertebra). |
| Poor 3D image quality | Check O-arm/C-arm positioning: center on the target. Remove extraneous metal from the field (retractors, clamps). Increase acquisition settings if image is noisy. |
| Reference frame not detected | Confirm line of sight between camera and reference frame spheres. Clean spheres. Check that the frame is within the camera's tracking volume. |
| Accuracy seems off after several screws | The spine may have shifted from retraction or reduction. Re-acquire a 3D spin. |
| Navigation freezes or loses tracking intermittently | Check for reflective surfaces in the OR (metal trays, fluid bags). Cover or reposition. Confirm spheres are clean and undamaged. |
| 3D spin does not transfer to nav system | Verify network/cable connection between the imaging system and the nav console. Restart the transfer. |

## Contraindications / Warnings

- Navigation is a surgical adjunct. It does not replace the need for the surgeon to independently verify screw position by anatomical landmarks, fluoroscopy, or other means.
- The reference frame must remain rigidly fixed to the patient throughout the navigated portion of the procedure. Any reference frame motion invalidates navigation.
- Do not rely solely on SpineMask level identification. Always independently verify levels (count from sacrum, check transitional anatomy, correlate with preoperative imaging).
- Intraoperative 3D imaging involves ionizing radiation. Follow ALARA principles.
- Navigation accuracy is valid only for the anatomy captured at the time of the 3D spin. Any surgical manipulation that alters spinal alignment (distraction, compression, reduction, derotation) after the spin makes the navigation data unreliable for the affected segments.

## Sizing/Specs

### System Specifications
- **Tracking technology:** Optical infrared (passive reflective sphere arrays)
- **Navigation platform:** Stryker proprietary surgical navigation console
- **Software:** SpineMap 3D with SpineMask vertebral segmentation module
- **Display:** Touchscreen interface with multiplanar reconstruction (axial, sagittal, coronal views)
- **Registration method:** Automatic (intraoperative 3D imaging); no manual point-matching required
- **Application accuracy:** 1-2 mm typical (limited by 3D spin spatial resolution and reference frame stability)
- **Field of view per acquisition:** Approximately 6-8 vertebral levels (depends on imaging system)

### Imaging Compatibility
- Medtronic O-arm (O2 generation)
- Isocentric C-arms with 3D spin capability (e.g., Ziehm Vision FD 3D, Siemens Cios Spin)
- Dataset transfer: automatic via direct cable or network connection to the Stryker nav console

### Tracked Instruments
- Navigated probes, awls, taps, screwdrivers with passive reflective sphere arrays
- Instrument calibration via divot verification on the reference frame or dedicated jig

## Indications

- Image-guided pedicle screw placement (open, mini-open, or percutaneous) in cervical, thoracic, and lumbar spine
- Interbody fusion procedures (TLIF, PLIF, ALIF) requiring navigated cage placement or disc space entry
- Spinal decompression with navigation for level identification and decompression extent
- Multi-level and deformity surgery where positive level identification (SpineMask) reduces wrong-level risk
- Revision spine surgery with distorted anatomy
- Any instrumented spine procedure where real-time 3D image guidance is desired

## Compatible With

- **Navigation hardware:** Stryker surgical navigation system (NAV3i platform or current generation)
- **Imaging:** O-arm, 3D-capable C-arms (see Sizing/Specs above)
- **Implants:** Stryker spine implant systems (e.g., Serrato, Xia, Expedium-equivalent lines); the navigation instruments are Stryker-proprietary
- **Patient reference frames:** Stryker spinous process clamps, percutaneous reference pins
- **Robotic integration:** SpineMap 3D does not currently integrate with a robotic arm (Stryker's robotic spine offering is separate from SpineMap 3D)

## Use Notes

- SpineMask is the key differentiator: automatic vertebral body segmentation and level labeling reduces wrong-level surgery risk, especially in long constructs and deformity cases. However, the auto-labeling must always be verified by the surgeon (errors occur with transitional anatomy, severe deformity, or metal artifact).
- Registration is fully automatic when using intraoperative 3D imaging. No manual point-matching or surface-tracing is needed, which saves setup time and reduces a source of registration error.
- Each 3D spin delivers radiation roughly equivalent to a limited CT scan. Minimize re-spins; re-acquire only when the reference frame is disturbed or the spine has been manipulated (reduction, distraction).
- The system navigates on the intraoperative 3D dataset, not preoperative CT. This means the images reflect the patient's actual surgical position, which is an advantage over systems that register to preoperative imaging.
- For long constructs exceeding the field of view, a second 3D spin centered on the remaining levels is required, with re-registration.
- Metal artifact from prior hardware degrades image quality and can confuse SpineMask segmentation. Navigate cautiously and verify all labels in revision cases.

## Key Differences vs Competitors

| Feature | Stryker SpineMap 3D | Medtronic StealthStation + O-arm | Brainlab Spine Navigation | Globus ExcelsiusGPS |
|---|---|---|---|---|
| Vertebral auto-labeling | Yes (SpineMask) | No (manual level identification) | No | No |
| Registration | Automatic (intraoperative 3D) | Automatic (intraoperative 3D) | Automatic or manual | Automatic (intraoperative 3D) |
| Robotic integration | No | Yes (Mazor X Stealth Edition) | Yes (Cirq robotic arm) | Yes (built-in robotic arm) |
| Tracking | Optical infrared | Optical infrared | Optical infrared | Robotic arm + optical |
| Third-party instrument support | Limited (Stryker ecosystem) | Yes (NavLock standard allows third-party instruments) | Yes (compatible instrument kits from multiple vendors) | Limited (Globus ecosystem) |
| Platform | Stryker proprietary | Medtronic proprietary | Brainlab proprietary | Globus proprietary |

- SpineMap 3D's SpineMask auto-labeling is unique among current navigation platforms. No competitor offers automated vertebral segmentation and level identification.
- The main limitation vs Medtronic is the lack of robotic integration. Medtronic offers the Mazor X Stealth Edition as an add-on to StealthStation; Stryker does not have an equivalent robotic spine system integrated with SpineMap 3D.
- Compared to Brainlab, SpineMap 3D is a closed ecosystem (Stryker instruments only). Brainlab supports a wider range of third-party instrument manufacturers.
- All optical navigation systems share the same fundamental limitations: line-of-sight requirements, reference frame stability dependence, and accuracy degradation with patient movement.

## Also Known As

- SpineMap 3D
- SpineMask
- Stryker Spine Nav
- Stryker 3D Navigation
- Stryker NAV3i (when running on the NAV3i platform)
