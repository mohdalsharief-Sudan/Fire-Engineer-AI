import sys, traceback

modules = ['library_db', 'pricing_engine', 'pricing_tab', 'cad_tool_tab', 'equipment_tab']
ok = True
print('=== Stage 1: import ===')
for m in modules:
    try:
        __import__(m); print(f'  OK {m}')
    except Exception as e:
        print(f'  FAIL {m}: {e}'); ok = False

if ok:
    print()
    print('=== Stage 2: quick widgets ===')
    try:
        from library_db import get_library_session, LibraryEquipment
        s = get_library_session(); n = s.query(LibraryEquipment).count()
        print(f'  library_db: {n} equipment rows')
    except Exception as e:
        print(f'  library_db FAIL: {e}'); traceback.print_exc()
    try:
        from pricing_engine import compute_quote_totals, generate_quote_number
        t = compute_quote_totals([{'qty': 2, 'supply_price_sar': 100, 'install_price_sar': 50}])
        print(f'  pricing_engine: grand_total={t["grand_total"]}  quote={generate_quote_number()}')
    except Exception as e:
        print(f'  pricing_engine FAIL: {e}'); traceback.print_exc()
    try:
        from pricing_tab import PricingTab
        w = PricingTab(); w._new_quote(); w._compute_totals()
        print(f'  pricing_tab: fresh quote items={len(w._current_items)}')
    except Exception as e:
        print(f'  pricing_tab FAIL: {e}'); traceback.print_exc()
    try:
        from cad_tool_tab import CadToolTab, EZDXF_AVAILABLE
        w = CadToolTab()
        print(f'  cad_tool_tab: Ezdxf={EZDXF_AVAILABLE}, widget OK')
    except Exception as e:
        print(f'  cad_tool_tab FAIL: {e}'); traceback.print_exc()
    try:
        from equipment_tab import EquipmentTab
        w = EquipmentTab()
        print(f'  equipment_tab: filtered={len(w._filtered_items)}')
    except Exception as e:
        print(f'  equipment_tab FAIL: {e}'); traceback.print_exc()
    print('DONE')
