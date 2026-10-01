from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
template=(ROOT/'preview.template.html').read_text()
assert template.count('<!-- HERO_SVG -->')==1
svg=(ROOT/'assets/observatory.svg').read_text()
(ROOT/'preview.html').write_text(template.replace('<!-- HERO_SVG -->',svg))
print('Regenerated interactive preview')
