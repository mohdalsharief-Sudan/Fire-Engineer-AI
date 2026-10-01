import sys, traceback
sys.path.insert(0, 'D:/My-GitHub/GitHub/FireEngineerAI')

print('=== Testing all modules ===')
modules = ['library_db', 'pricing_engine', 'pricing_tab', 'cad_tool_tab', 'equipment_tab']
for m in modules:
    try:
        __import__(m)
        print(f'  import {m}: OK')
    except Exception as e:
        print(f'  FAIL {m}: {e}')
        sys.exit(1)

print()
print('=== library_db ===')
from library_db import get_library_session, LibraryEquipment
s = get_library_session()
n = s.query(LibraryEquipment).count()
print(f'  {n} rows')
s.close()

print()
print('=== equipment_tab ===')
from equipment_tab import EquipmentTab
w = EquipmentTab()
print(f'  all={len(w.all_equipment)} filtered={len(w.filtered_equipment)}')

print()
print('=== pricing_tab ===')
from pricing_tab import PricingTab
w = PricingTab()
print('  OK')

print()
print('=== cad_tool_tab ===')
from cad_tool_tab import CadToolTab
w = CadToolTab()
print('  OK')

print()
print('ALL TESTS PASSED')
