"""
Coaxial compatibility query tool for neurointerventional device stacks.

Usage:
    python -m pipeline.compat_query                      # Show all devices
    python -m pipeline.compat_query --fits-through "SOFIA 6F"   # What fits inside SOFIA 6F?
    python -m pipeline.compat_query --accepts "Trevo Trak 21"   # What can Trevo Trak 21 fit inside?
    python -m pipeline.compat_query --stack "SOFIA 6F"          # Build a full stack from this intermediate
    python -m pipeline.compat_query --gaps                      # Show devices missing dimensional data
"""
import json
import argparse
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "compatibility" / "thrombectomy_stack.json"


def load_devices():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [d for d in data["devices"] if "_section" not in d]


def fits_through(inner_device, outer_device):
    """Check if inner_device OD fits through outer_device ID."""
    inner_od = inner_device.get("od_prox_inch") or inner_device.get("od_inch")
    outer_id = outer_device.get("id_inch")
    if inner_od is None or outer_id is None:
        return None  # unknown
    return inner_od < outer_id


def find_fits_through(target_name, devices):
    """Find all devices that fit inside the named device."""
    target = next((d for d in devices if d["name"].lower() == target_name.lower()), None)
    if not target:
        print(f"Device not found: {target_name}")
        print(f"Available: {', '.join(d['name'] for d in devices)}")
        return
    if target.get("id_inch") is None:
        print(f"{target['name']}: ID unknown, cannot check compatibility")
        return

    print(f"\n  What fits through {target['name']}? (ID = {target['id_inch']}\")")
    print(f"  {'='*60}")

    results = {"yes": [], "no": [], "unknown": []}
    for d in devices:
        if d["name"] == target["name"]:
            continue
        od = d.get("od_prox_inch") or d.get("od_inch")
        if od is None:
            results["unknown"].append((d["name"], d["category"], "OD unknown"))
        elif od < target["id_inch"]:
            clearance = target["id_inch"] - od
            results["yes"].append((d["name"], d["category"], od, clearance))
        else:
            results["no"].append((d["name"], d["category"], od))

    if results["yes"]:
        print(f"\n  YES (fits):")
        for name, cat, od, clearance in sorted(results["yes"], key=lambda x: -x[3]):
            print(f"    {name:<30} {cat:<20} OD={od:.3f}\"  clearance={clearance:.3f}\"")

    if results["no"]:
        print(f"\n  NO (too large):")
        for name, cat, od in sorted(results["no"], key=lambda x: x[2]):
            print(f"    {name:<30} {cat:<20} OD={od:.3f}\"")

    if results["unknown"]:
        print(f"\n  UNKNOWN (missing data):")
        for name, cat, reason in results["unknown"]:
            print(f"    {name:<30} {cat:<20} {reason}")


def find_accepts(target_name, devices):
    """Find all devices the named device fits inside of."""
    target = next((d for d in devices if d["name"].lower() == target_name.lower()), None)
    if not target:
        print(f"Device not found: {target_name}")
        return
    od = target.get("od_prox_inch") or target.get("od_inch")
    if od is None:
        print(f"{target['name']}: OD unknown, cannot check compatibility")
        return

    print(f"\n  What can accept {target['name']}? (OD = {od}\")")
    print(f"  {'='*60}")

    for d in devices:
        if d["name"] == target["name"]:
            continue
        d_id = d.get("id_inch")
        if d_id is None:
            print(f"    {d['name']:<30} {d['category']:<20} ID unknown")
        elif d_id > od:
            clearance = d_id - od
            print(f"    {d['name']:<30} {d['category']:<20} ID={d_id:.3f}\"  clearance={clearance:.3f}\"  YES")
        else:
            print(f"    {d['name']:<30} {d['category']:<20} ID={d_id:.3f}\"  TOO SMALL")


def build_stack(intermediate_name, devices):
    """Build all valid thrombectomy stacks from a given intermediate catheter."""
    intermediate = next((d for d in devices if d["name"].lower() == intermediate_name.lower()), None)
    if not intermediate:
        print(f"Device not found: {intermediate_name}")
        return

    int_id = intermediate.get("id_inch")
    if int_id is None:
        print(f"{intermediate['name']}: ID unknown")
        return

    # Find microcatheters that fit through the intermediate
    micros = []
    for d in devices:
        if d.get("role") != "delivery_microcatheter":
            continue
        od = d.get("od_prox_inch") or d.get("od_inch")
        if od is not None and od < int_id:
            micros.append(d)

    # Find aspiration catheters that fit through the intermediate
    aspirations = []
    for d in devices:
        if d.get("role") != "aspiration_catheter":
            continue
        od = d.get("od_prox_inch") or d.get("od_inch")
        if od is not None and od < int_id:
            aspirations.append(d)

    # Find stent retrievers compatible with those microcatheters
    retrievers = [d for d in devices if d.get("role") == "thrombectomy_device"]

    print(f"\n  Thrombectomy stacks through {intermediate['name']} (ID={int_id}\")")
    print(f"  {'='*60}")

    print(f"\n  STENT RETRIEVER APPROACH (intermediate -> microcatheter -> device):")
    if micros:
        for mc in micros:
            mc_od = mc.get("od_prox_inch") or mc.get("od_inch")
            mc_id = mc.get("id_inch")
            print(f"    {intermediate['name']} -> {mc['name']} (OD={mc_od:.3f}\", ID={mc_id:.3f}\")")
            for sr in retrievers:
                min_cath = sr.get("min_catheter_id_inch")
                if min_cath and mc_id and mc_id >= min_cath:
                    print(f"      -> {sr['name']} ({sr.get('device_sizes_mm', '?')})")
    else:
        print("    No compatible microcatheters found (or missing OD data)")

    print(f"\n  DIRECT ASPIRATION (ADAPT) (intermediate -> aspiration catheter):")
    if aspirations:
        for asp in aspirations:
            asp_od = asp.get("od_prox_inch") or asp.get("od_inch")
            print(f"    {intermediate['name']} -> {asp['name']} (OD={asp_od:.3f}\")")
    else:
        print("    No compatible aspiration catheters found (or missing OD data)")

    print(f"\n  MINIMUM GUIDE CATHETER:")
    min_guide = intermediate.get("min_guide_id_inch")
    if min_guide:
        print(f"    Guide catheter ID >= {min_guide}\" required for {intermediate['name']}")
    else:
        int_od = intermediate.get("od_prox_inch") or intermediate.get("od_inch")
        if int_od:
            print(f"    Guide catheter ID > {int_od}\" required (based on intermediate OD)")
        else:
            print(f"    Unknown (intermediate OD not available)")


def show_gaps(devices):
    """Show devices missing critical dimensional data."""
    print(f"\n  Devices with missing dimensional data:")
    print(f"  {'='*60}")
    for d in devices:
        missing = []
        if d.get("id_inch") is None and d.get("role") != "thrombectomy_device":
            missing.append("ID")
        if d.get("od_inch") is None and d.get("role") != "thrombectomy_device":
            missing.append("OD")
        if not d.get("length_cm"):
            missing.append("length")
        if missing:
            print(f"    {d['name']:<30} {d['category']:<20} missing: {', '.join(missing)}")


def show_all(devices):
    """Show all devices with their dimensional data."""
    print(f"\n  {'Name':<30} {'Category':<20} {'ID':>8} {'OD':>8} {'OD(prox)':>10} {'Lengths'}")
    print(f"  {'-'*90}")
    for d in devices:
        id_val = f"{d['id_inch']:.3f}\"" if d.get("id_inch") else "?"
        od_val = f"{d['od_inch']:.3f}\"" if d.get("od_inch") else "?"
        od_p = f"{d['od_prox_inch']:.3f}\"" if d.get("od_prox_inch") else "-"
        lengths = str(d.get("length_cm", "?"))
        print(f"  {d['name']:<30} {d['category']:<20} {id_val:>8} {od_val:>8} {od_p:>10} {lengths}")


def main():
    parser = argparse.ArgumentParser(description="Neurointerventional coaxial compatibility query")
    parser.add_argument("--fits-through", metavar="DEVICE", help="What fits inside this device?")
    parser.add_argument("--accepts", metavar="DEVICE", help="What can this device fit inside?")
    parser.add_argument("--stack", metavar="DEVICE", help="Build full thrombectomy stacks from this intermediate")
    parser.add_argument("--gaps", action="store_true", help="Show devices missing data")
    args = parser.parse_args()

    devices = load_devices()

    if args.fits_through:
        find_fits_through(args.fits_through, devices)
    elif args.accepts:
        find_accepts(args.accepts, devices)
    elif args.stack:
        build_stack(args.stack, devices)
    elif args.gaps:
        show_gaps(devices)
    else:
        show_all(devices)


if __name__ == "__main__":
    main()
