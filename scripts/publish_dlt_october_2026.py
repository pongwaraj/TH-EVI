"""Insert the official October DLT snapshot without overwriting existing records."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from th_evi.db import DLTProvinceFleetSnapshot, ReferenceSource
from scripts.publish_chiang_mai_pilot import load_database_url

SOURCE = 'DLT fuel31Oct26_W.xlsx'
URL = 'https://web.dlt.go.th/statistics/load_file_select_new_car.php?t=3&data_file=1340'
INTS = ('source_year_be', 'total_vehicles', 'gasoline', 'diesel', 'bev', 'hev_gasoline',
        'hev_diesel', 'phev_gasoline', 'phev_diesel')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env.vercel.production')
    args = parser.parse_args()
    url = load_database_url(args.env_file)
    if not (make_url(url).host or '').endswith('.neon.tech'):
        raise ValueError('Refusing an unexpected database host')
    with (ROOT / 'data/evhub_dlt_fleet_2569_10.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 152 or any(r['source_month'] != '2569-10' for r in rows):
        raise ValueError('Unexpected October snapshot')
    engine = create_engine(url, connect_args={'connect_timeout': 15})
    with Session(engine) as db, db.begin():
        db.execute(text("SET LOCAL lock_timeout = '10s'"))
        db.execute(text("SET LOCAL statement_timeout = '90s'"))
        existing = list(db.scalars(select(DLTProvinceFleetSnapshot).where(DLTProvinceFleetSnapshot.source_month == '2569-10')))
        by_key = {(x.province, x.vehicle_segment): x for x in existing}
        conflicts = []
        for row in rows:
            record = by_key.get((row['province'], row['vehicle_segment']))
            if record and (any(getattr(record, k) != int(row[k]) for k in INTS)
                           or abs((record.bev_share or 0) - float(row['bev_share'])) > 1e-9):
                conflicts.append((row['province'], row['vehicle_segment']))
        if conflicts:
            raise ValueError(f'Existing October records differ; no changes made: {conflicts}')
        missing = [r for r in rows if (r['province'], r['vehicle_segment']) not in by_key]
        report = {'mode': 'apply' if args.apply else 'dry_run', 'existing': len(existing),
                  'matching': len(rows) - len(missing), 'to_insert': len(missing), 'conflicts': len(conflicts)}
        if args.apply:
            source = db.scalar(select(ReferenceSource).where(ReferenceSource.source_name == SOURCE))
            if source and source.source_url != URL:
                raise ValueError('Existing source has an unexpected URL')
            if not source:
                source = ReferenceSource(source_name=SOURCE, source_type='official', source_url=URL,
                                         confidence='high', notes='Cumulative DLT vehicle registrations at 31 October 2026.')
                db.add(source); db.flush()
            for row in missing:
                payload = {key: row[key] for key in ('province','source_month','vehicle_segment','source_project','source_file')}
                payload.update({key:int(row[key]) for key in INTS})
                payload.update(bev_share=float(row['bev_share']), source_id=source.id, source_url=URL,
                    source_scope='Official cumulative provincial vehicle registration; motor vehicle law and Ror.1 are separate segments.',
                    notes='Snapshot date: 31 October 2026. Registration stock is not charging demand.')
                db.add(DLTProvinceFleetSnapshot(**payload))
            db.flush()
            actual = list(db.scalars(select(DLTProvinceFleetSnapshot).where(DLTProvinceFleetSnapshot.source_month == '2569-10')))
            for row in rows:
                record = next(x for x in actual if (x.province,x.vehicle_segment)==(row['province'],row['vehicle_segment']))
                assert all(getattr(record,k)==int(row[k]) for k in INTS)
            report['readback_verified'] = len(rows)
        print(json.dumps(report))
    engine.dispose()


if __name__ == '__main__':
    main()
