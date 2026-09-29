"""Build a tiny, deterministic display dataset. Never changes source data."""
import hashlib
import json
from pathlib import Path
import shutil

FRONT = Path(__file__).resolve().parents[1]
ROOT = FRONT.parent
SLUGS = [
    'fanagoriya-cru-lermont-chardonnay-shardone-beloe-suhoe-14',
    'usadba-markoth-shardone-beloe-suhoe-12',
    'znoj-denisov-vajneri',
    'cantiani-riesling-rkatsiteli',
    'abrau-dyurso-abrau-kupazh-svetlyy-suhoe-shardone-beloe-125',
]
FIELDS = 'slug name winery_name region category color_category sweetness_from_category grapes description alcohol_percent alcohol_max_percent serving_temperature_c food_pairings public_rating guide_rating similar_wine_slugs source_url fetched_at'.split()
source = ROOT / 'data/catalog_v1/catalog.jsonl'
rows = {r['slug']: r for r in map(json.loads, source.read_text().splitlines())}
output = FRONT / 'public/demo'
output.mkdir(parents=True, exist_ok=True)
cards, manifest = [], []
for slug in SLUGS:
    row = rows[slug]
    assert row['reference_usable'], slug
    image = ROOT / row['image_local_path']
    target = slug + image.suffix
    shutil.copyfile(image, output / target)
    card = {key: row.get(key) for key in FIELDS}
    card['image_url'] = '/demo/' + target
    card['similar_wine_slugs'] = [s for s in (row.get('similar_wine_slugs') or []) if s in SLUGS]
    cards.append(card)
    manifest.append({'slug': slug, 'source_image': row['image_local_path'], 'sha256': hashlib.sha256(image.read_bytes()).hexdigest(), 'bytes': image.stat().st_size})
(output / 'cards.json').write_text(json.dumps(cards, ensure_ascii=False, indent=2) + '\n')
(FRONT / 'scripts/demo-manifest.json').write_text(json.dumps({'source': str(source.relative_to(ROOT)), 'catalog_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'images': manifest}, ensure_ascii=False, indent=2) + '\n')
print(f'{len(cards)} cards; {sum(r["bytes"] for r in manifest):,} image bytes')
