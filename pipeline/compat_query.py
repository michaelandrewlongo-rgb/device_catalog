"""
Coaxial compatibility query tool for neurointerventional device stacks.

Usage:
    python -m pipeline.compat_query
    python -m pipeline.compat_query --fits-through "SOFIA 6F"
    python -m pipeline.compat_query --accepts "Trevo Trak 21"
    python -m pipeline.compat_query --stack "SOFIA 6F"
    python -m pipeline.compat_query --case "SOFIA 6F"
    python -m pipeline.compat_query --gaps
"""

import argparse
import difflib
import json
import re
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "compatibility" / "thrombectomy_stack.json"
KNOWN_VERIFICATION_STATUSES = {"verified", "partial", "inferred_existing", "needs_source"}


def load_devices():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [d for d in data["devices"] if "_section" not in d]


def normalize_name(value):
    """Normalize device names for forgiving CLI lookup."""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def verification_status(device):
    """Return a coarse source confidence label for display and triage."""
    explicit = device.get("verification_status")
    if explicit in KNOWN_VERIFICATION_STATUSES:
        return explicit

    source = (device.get("source") or "").lower()
    if source.startswith("needs"):
        return "needs_source"
    if "inferred" in source:
        return "inferred_existing"
    if "partial" in source:
        return "partial"
    return "verified"


def format_inches(value):
    if value is None:
        return "?"
    return f'{value:.3f}"'


def device_od(device):
    """Use proximal OD when available because it is the limiting coaxial segment."""
    return device.get("od_prox_inch") or device.get("od_inch")


def source_label(device):
    status = verification_status(device).replace("_", " ")
    source = device.get("source", "unknown")
    url = device.get("source_url")
    if url:
        return f"{status}; {source}; {url}"
    return f"{status}; {source}"


def find_device(query, devices):
    """Find a device by exact, normalized, substring, or fuzzy name match."""
    normalized_query = normalize_name(query)
    normalized = {normalize_name(d["name"]): d for d in devices}

    if normalized_query in normalized:
        return normalized[normalized_query]

    substring_matches = [
        d for d in devices
        if normalized_query in normalize_name(d["name"])
        or normalize_name(d["name"]) in normalized_query
    ]
    if len(substring_matches) == 1:
        return substring_matches[0]

    close_names = difflib.get_close_matches(
        normalized_query,
        list(normalized),
        n=3,
        cutoff=0.65,
    )
    if len(close_names) == 1:
        return normalized[close_names[0]]

    suggestions = substring_matches[:3] or [normalized[name] for name in close_names]
    if suggestions:
        print(f"Device not found unambiguously: {query}")
        print("Did you mean: " + ", ".join(d["name"] for d in suggestions))
    else:
        print(f"Device not found: {query}")
        print(f"Available: {', '.join(d['name'] for d in devices)}")
    return None


def fit_details(inner_device, outer_device):
    """Return fit status plus the dimensions used to make the decision."""
    inner_od = device_od(inner_device)
    outer_id = outer_device.get("id_inch")
    if inner_od is None or outer_id is None:
        return {
            "status": "unknown",
            "inner_od": inner_od,
            "outer_id": outer_id,
            "clearance": None,
            "reason": "missing OD" if inner_od is None else "missing ID",
        }

    clearance = outer_id - inner_od
    return {
        "status": "fits" if clearance > 0 else "too_large",
        "inner_od": inner_od,
        "outer_id": outer_id,
        "clearance": clearance,
        "reason": None,
    }


def fits_through(inner_device, outer_device):
    """Check if inner_device OD fits through outer_device ID."""
    result = fit_details(inner_device, outer_device)
    if result["status"] == "unknown":
        return None
    return result["status"] == "fits"


def find_fits_through(target_name, devices):
    """Find all devices that fit inside the named device."""
    target = find_device(target_name, devices)
    if not target:
        return
    if target.get("id_inch") is None:
        print(f"{target['name']}: ID unknown, cannot check compatibility")
        print(f"  Source: {source_label(target)}")
        return

    print(f"\n  What fits through {target['name']}? (ID = {format_inches(target['id_inch'])})")
    print(f"  Source: {source_label(target)}")
    print(f"  {'=' * 60}")

    results = {"yes": [], "no": [], "unknown": []}
    for device in devices:
        if device["name"] == target["name"]:
            continue
        result = fit_details(device, target)
        if result["status"] == "unknown":
            results["unknown"].append((device, result))
        elif result["status"] == "fits":
            results["yes"].append((device, result))
        else:
            results["no"].append((device, result))

    if results["yes"]:
        print("\n  YES (fits):")
        for device, result in sorted(results["yes"], key=lambda item: -item[1]["clearance"]):
            print(
                f"    {device['name']:<30} {device['category']:<20} "
                f"OD={format_inches(result['inner_od'])}  "
                f"clearance={format_inches(result['clearance'])}  [{source_label(device)}]"
            )

    if results["no"]:
        print("\n  NO (too large):")
        for device, result in sorted(results["no"], key=lambda item: item[1]["inner_od"]):
            print(
                f"    {device['name']:<30} {device['category']:<20} "
                f"OD={format_inches(result['inner_od'])}  [{source_label(device)}]"
            )

    if results["unknown"]:
        print("\n  UNKNOWN (missing data):")
        for device, result in results["unknown"]:
            print(
                f"    {device['name']:<30} {device['category']:<20} "
                f"{result['reason']}  [{source_label(device)}]"
            )


def find_accepts(target_name, devices):
    """Find all devices the named device fits inside of."""
    target = find_device(target_name, devices)
    if not target:
        return
    od = device_od(target)
    if od is None:
        print(f"{target['name']}: OD unknown, cannot check compatibility")
        print(f"  Source: {source_label(target)}")
        return

    print(f"\n  What can accept {target['name']}? (OD = {format_inches(od)})")
    print(f"  Source: {source_label(target)}")
    print(f"  {'=' * 60}")

    for device in devices:
        if device["name"] == target["name"]:
            continue
        result = fit_details(target, device)
        if result["status"] == "unknown":
            print(
                f"    {device['name']:<30} {device['category']:<20} "
                f"{result['reason']}  [{source_label(device)}]"
            )
        elif result["status"] == "fits":
            print(
                f"    {device['name']:<30} {device['category']:<20} "
                f"ID={format_inches(result['outer_id'])}  "
                f"clearance={format_inches(result['clearance'])}  YES  [{source_label(device)}]"
            )
        else:
            print(
                f"    {device['name']:<30} {device['category']:<20} "
                f"ID={format_inches(result['outer_id'])}  TOO SMALL  [{source_label(device)}]"
            )


def build_stack(intermediate_name, devices):
    """Build all valid thrombectomy stacks from a given intermediate catheter."""
    intermediate = find_device(intermediate_name, devices)
    if not intermediate:
        return

    int_id = intermediate.get("id_inch")
    if int_id is None:
        print(f"{intermediate['name']}: ID unknown")
        print(f"  Source: {source_label(intermediate)}")
        return

    micros = []
    for device in devices:
        if device.get("role") != "delivery_microcatheter":
            continue
        od = device_od(device)
        if od is not None and od < int_id:
            micros.append(device)

    aspirations = []
    for device in devices:
        if device.get("role") != "aspiration_catheter":
            continue
        od = device_od(device)
        if od is not None and od < int_id:
            aspirations.append(device)

    retrievers = [d for d in devices if d.get("role") == "thrombectomy_device"]

    print(f"\n  Thrombectomy stacks through {intermediate['name']} (ID={format_inches(int_id)})")
    print(f"  Source: {source_label(intermediate)}")
    print(f"  {'=' * 60}")

    print("\n  STENT RETRIEVER APPROACH (intermediate -> microcatheter -> device):")
    if micros:
        for micro in micros:
            mc_od = device_od(micro)
            mc_id = micro.get("id_inch")
            print(
                f"    {intermediate['name']} -> {micro['name']} "
                f"(OD={format_inches(mc_od)}, ID={format_inches(mc_id)})  "
                f"[{source_label(micro)}]"
            )
            for retriever in retrievers:
                min_cath = retriever.get("min_catheter_id_inch")
                if min_cath and mc_id and mc_id >= min_cath:
                    print(
                        f"      -> {retriever['name']} "
                        f"({retriever.get('device_sizes_mm', '?')})  "
                        f"[{source_label(retriever)}]"
                    )
    else:
        print("    No compatible microcatheters found (or missing OD data)")

    print("\n  DIRECT ASPIRATION (ADAPT) (intermediate -> aspiration catheter):")
    if aspirations:
        for aspiration in aspirations:
            asp_od = device_od(aspiration)
            print(
                f"    {intermediate['name']} -> {aspiration['name']} "
                f"(OD={format_inches(asp_od)})  [{source_label(aspiration)}]"
            )
    else:
        print("    No compatible aspiration catheters found (or missing OD data)")

    print("\n  MINIMUM GUIDE CATHETER:")
    min_guide = intermediate.get("min_guide_id_inch")
    if min_guide:
        print(f"    Guide catheter ID >= {format_inches(min_guide)} required for {intermediate['name']}")
    else:
        int_od = device_od(intermediate)
        if int_od:
            print(f"    Guide catheter ID > {format_inches(int_od)} required (based on intermediate OD)")
        else:
            print("    Unknown (intermediate OD not available)")


def gap_kind(device, field):
    """Classify missing data by whether it blocks fit math or adds context."""
    role = device.get("role")
    if role == "thrombectomy_device":
        return "critical" if field == "min_catheter_id_inch" else "context"
    if field == "id_inch" and role in {
        "guide_catheter",
        "balloon_guide_catheter",
        "intermediate_catheter",
        "large_bore_intermediate",
        "aspiration_catheter",
        "delivery_microcatheter",
    }:
        return "critical"
    if field in {"od_inch", "od_prox_inch"} and role in {
        "intermediate_catheter",
        "large_bore_intermediate",
        "aspiration_catheter",
        "delivery_microcatheter",
    }:
        return "critical"
    return "context"


def missing_fields(device):
    missing = []
    if device.get("role") == "thrombectomy_device":
        if device.get("min_catheter_id_inch") is None:
            missing.append("min_catheter_id_inch")
    else:
        if device.get("id_inch") is None:
            missing.append("id_inch")
        if device.get("od_inch") is None and device.get("od_prox_inch") is None:
            missing.append("od_inch")
    if not device.get("length_cm"):
        missing.append("length_cm")
    return missing


def show_gaps(devices):
    """Show devices missing or carrying unresolved dimensional data."""
    grouped = {"critical": [], "context": [], "unresolved": []}
    for device in devices:
        for field in missing_fields(device):
            grouped[gap_kind(device, field)].append((device, field))
        if verification_status(device) != "verified":
            grouped["unresolved"].append((device, verification_status(device)))

    print("\n  Devices with missing or unresolved dimensional data:")
    print(f"  {'=' * 60}")

    for label in ("critical", "context", "unresolved"):
        if not grouped[label]:
            continue
        print(f"\n  {label.upper()}:")
        for device, detail in grouped[label]:
            if label == "unresolved":
                print(
                    f"    {device['name']:<30} {device['category']:<20} "
                    f"status: {detail}  [{source_label(device)}]"
                )
            else:
                print(
                    f"    {device['name']:<30} {device['category']:<20} "
                    f"missing: {detail}  [{source_label(device)}]"
                )


def build_case(device_name, devices):
    """Print a concise case-oriented compatibility summary for a selected device."""
    target = find_device(device_name, devices)
    if not target:
        return

    print(f"\n  Case device: {target['name']}")
    print(f"  Category: {target['category']} / {target['role']}")
    print(
        f"  ID: {format_inches(target.get('id_inch'))}  "
        f"OD: {format_inches(target.get('od_inch'))}  "
        f"OD(prox): {format_inches(target.get('od_prox_inch'))}"
    )
    print(f"  Source: {source_label(target)}")

    gaps = missing_fields(target)
    if gaps:
        print(f"  Missing: {', '.join(gaps)}")

    print("\n  Accepting outer devices:")
    od = device_od(target)
    if od is None:
        print("    Unknown because selected device OD is missing.")
    else:
        accepted = []
        unknown = []
        for device in devices:
            if device["name"] == target["name"]:
                continue
            result = fit_details(target, device)
            if result["status"] == "fits":
                accepted.append((device, result))
            elif result["status"] == "unknown":
                unknown.append((device, result))
        for device, result in sorted(accepted, key=lambda item: -item[1]["clearance"])[:12]:
            print(
                f"    {device['name']:<30} "
                f"clearance={format_inches(result['clearance'])}  [{source_label(device)}]"
            )
        if unknown:
            print(f"    Unknown against {len(unknown)} devices with missing ID data.")

    print("\n  Inner devices that fit through it:")
    if target.get("id_inch") is None:
        print("    Unknown because selected device ID is missing.")
        return

    inner_matches = []
    unknown = []
    for device in devices:
        if device["name"] == target["name"]:
            continue
        result = fit_details(device, target)
        if result["status"] == "fits":
            inner_matches.append((device, result))
        elif result["status"] == "unknown":
            unknown.append((device, result))
    for device, result in sorted(inner_matches, key=lambda item: -item[1]["clearance"])[:12]:
        print(
            f"    {device['name']:<30} "
            f"clearance={format_inches(result['clearance'])}  [{source_label(device)}]"
        )
    if unknown:
        print(f"    Unknown for {len(unknown)} devices with missing OD data.")


def show_all(devices):
    """Show all devices with their dimensional data."""
    print(
        f"\n  {'Name':<30} {'Category':<20} {'ID':>8} {'OD':>8} "
        f"{'OD(prox)':>10} {'Status':<18} {'Lengths'}"
    )
    print(f"  {'-' * 110}")
    for device in devices:
        id_val = format_inches(device.get("id_inch"))
        od_val = format_inches(device.get("od_inch"))
        od_p = format_inches(device.get("od_prox_inch")) if device.get("od_prox_inch") else "-"
        lengths = str(device.get("length_cm", "?"))
        print(
            f"  {device['name']:<30} {device['category']:<20} "
            f"{id_val:>8} {od_val:>8} {od_p:>10} "
            f"{verification_status(device):<18} {lengths}"
        )


def main():
    parser = argparse.ArgumentParser(description="Neurointerventional coaxial compatibility query")
    parser.add_argument("--fits-through", metavar="DEVICE", help="What fits inside this device?")
    parser.add_argument("--accepts", metavar="DEVICE", help="What can this device fit inside?")
    parser.add_argument("--stack", metavar="DEVICE", help="Build full thrombectomy stacks from this intermediate")
    parser.add_argument("--case", metavar="DEVICE", help="Show a case-oriented summary for one device")
    parser.add_argument("--gaps", action="store_true", help="Show devices missing data")
    args = parser.parse_args()

    devices = load_devices()

    if args.fits_through:
        find_fits_through(args.fits_through, devices)
    elif args.accepts:
        find_accepts(args.accepts, devices)
    elif args.stack:
        build_stack(args.stack, devices)
    elif args.case:
        build_case(args.case, devices)
    elif args.gaps:
        show_gaps(devices)
    else:
        show_all(devices)


if __name__ == "__main__":
    main()
