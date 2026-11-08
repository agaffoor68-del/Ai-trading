from backend.indicator_engine import INDICATOR_REGISTRY
print(f'Indicators registered: {len(INDICATOR_REGISTRY)}')
print('Categories:', list(set(i['category'] for i in INDICATOR_REGISTRY.values())))
print()
print('Indicator details:')
for name, info in INDICATOR_REGISTRY.items():
    print(f"  {name}: {info['category']} - outputs: {info['output_cols']}")