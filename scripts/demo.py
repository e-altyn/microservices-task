import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8000')
    args = parser.parse_args()

    def api(path, data=None):
        request = Request(args.url.rstrip('/') + '/api' + path,
                          data=json.dumps(data).encode() if data is not None else None,
                          headers={'Content-Type':'application/json'})
        with urlopen(request, timeout=130) as response:
            return json.load(response)

    print('Services:', api('/system'))
    dataset = api('/datasets/collect', {'batch_number':1})
    print('1. Dataset:', dataset['id'], 'rows:', dataset['row_count'])
    model = api('/models', {'name':'Демонстрация MVP'})
    trained = api(f"/models/{model['id']}/train", {'dataset_id':dataset['id']})
    print('2. Trained:', trained['status'])
    records = api(f"/datasets/{dataset['id']}")['records'][:3]
    for row in records:
        row.pop('loan_status', None)
    predictions = api(f"/models/{model['id']}/predict", {'records':records})
    print('3. Predictions:', json.dumps(predictions['predictions'], indent=2))
    summary = api(f"/models/{model['id']}")
    print('4. Evaluation:', json.dumps(summary['metrics'], indent=2))
    print('Model ID:', model['id'])


if __name__ == '__main__':
    try:
        main()
    except HTTPError as exc:
        raise SystemExit(f'HTTP {exc.code}: {exc.read().decode()}') from exc
    except URLError as exc:
        raise SystemExit(f'Cannot connect: {exc.reason}. Start docker compose first.') from exc
