import json
from pathlib import Path

import pytest
from scripts.evaluate import summarize
from openjev.schema import SystemOneRequest


def test_metrics_use_probabilities_and_observed_outcomes_not_confidence():
    item = {'request': {'questions': {'c': {'type': 'choice'}, 'n': {'type': 'noul'},
                                     's': {'type': 'score', 'criteria': ['low', 'mid', 'high']}}},
            'expected': {'c': 'yes', 'n': False, 's': 2}}
    response = {'answers': {'c': {'choice': 'yes', 'probabilities': {'yes': .8, 'no': .2}, 'confidence': .01},
                            'n': {'noul': .75}, 's': {'score': 1.5}}}
    report = summarize([(item, response)])
    assert report['choice']['accuracy'] == 1
    assert report['choice']['brier_sum_over_classes'] == pytest.approx(.08)
    assert report['choice']['top_label_ece_10_bins'] == pytest.approx(.2)
    assert report['noul']['accuracy_at_0_5'] == 0
    assert report['noul']['brier'] == .5625
    assert report['noul']['ece_10_bins'] == .75
    assert report['score']['mae_in_rubric_levels'] == .5


def test_perfect_predictions_at_probability_one_stay_in_last_ece_bin():
    item = {'request': {'questions': {'n': {'type': 'noul'}}}, 'expected': {'n': True}}
    report = summarize([(item, {'answers': {'n': {'noul': 1.0}}})])
    assert report['noul']['ece_10_bins'] == 0
    assert report['choice']['accuracy'] is None
    with pytest.raises(ValueError, match='IDs'):
        summarize([(item, {'answers': {}})])


def test_smoke_fixtures_are_valid_api_requests_with_labels_for_every_question():
    for line in Path('eval/smoke.jsonl').read_text().splitlines():
        item = json.loads(line)
        body = SystemOneRequest(**item['request'])
        assert set(body.questions) == set(item['expected'])


def test_nll_slices_null_labels_and_fractional_score_labels_are_explicit():
    item = {'id': 'boundary', 'slices': ['zh', 'negation'], 'request': {'questions': {
        'c': {'type': 'choice', 'criteria': {'yes': 'Yes', 'unknown': 'No evidence'}},
        'n': {'type': 'noul'}, 's': {'type': 'score', 'criteria': ['low', 'high']}}},
        'expected': {'c': 'unknown', 'n': None, 's': .5}}
    result = {'answers': {'c': {'choice': 'unknown', 'probabilities': {'yes': .1, 'unknown': .9}},
                          'n': {'noul': .99}, 's': {'score': .75, 'probabilities': {'0': .25, '1': .75}}}}
    report = summarize([(item, result)])
    import math
    assert report['choice']['nll'] == pytest.approx(-math.log(.9))
    assert report['noul']['n'] == 0
    assert report['noul']['unlabeled'] == 1
    assert report['score']['mae_in_rubric_levels'] == .25
    assert report['score']['nll_n'] == 0
    assert report['score']['fractional_label_questions'] == 1
    assert report['slices']['negation']['by_type']['choice']['n'] == 1


def test_invalid_question_results_are_recorded_without_losing_good_questions():
    item = {'id': 'bad', 'request': {'questions': {'a': {'type': 'noul'}, 'b': {'type': 'noul'}}}, 'expected': {'a': True, 'b': False}}
    report = summarize([(item, {'answers': {'a': {'noul': .8}, 'b': {'noul': -1}}})], strict=False)
    assert report['noul']['n'] == 1
    assert report['errors'][0]['id'] == 'bad'
    assert report['errors'][0]['question'] == 'b'
    report = summarize([(item, {'answers': None})], strict=False)
    assert report['noul']['n'] == 0
    assert len(report['errors']) == 3


def test_cli_preserves_failure_records_and_returns_failure_exit_status(tmp_path, capsys):
    from scripts.evaluate import main
    items = [{'id': identifier, 'slices': ['failure_slice'], 'request': {'state': identifier, 'questions': {'n': {'type': 'noul', 'instructions': 'A claim.'}}}, 'expected': {'n': True}} for identifier in ['valid', 'invalid', 'unavailable']]
    data, responses, out = tmp_path / 'data.jsonl', tmp_path / 'responses.json', tmp_path / 'report.json'
    data.write_text(''.join(json.dumps(item) + '\n' for item in items))
    responses.write_text(json.dumps({'results': [
        {'id': 'valid', 'response': {'answers': {'n': {'noul': .8}}}},
        {'id': 'invalid', 'response': {'answers': {'n': {'noul': 'invalid'}}}},
        {'id': 'unavailable', 'error': {'message': 'HTTP 503'}}]}))
    assert main(['--data', str(data), '--responses', str(responses), '--out', str(out)]) == 1
    report = json.loads(out.read_text())
    assert [record['id'] for record in report['results']] == ['valid', 'invalid', 'unavailable']
    assert report['summary']['noul']['n'] == 1
    assert report['results'][1]['response']['answers']['n']['noul'] == 'invalid'
    assert report['results'][2]['error']
    assert report['summary']['slices']['failure_slice']['requests'] == 3
    assert report['summary']['slices']['failure_slice']['request_errors'] == 1
    assert report['summary']['slices']['failure_slice']['invalid_questions'] == 1
    capsys.readouterr()


def test_all_synthetic_fixtures_are_declared_and_schema_valid():
    for path in Path('eval').glob('*.jsonl'):
        for line in path.read_text().splitlines():
            item = json.loads(line)
            assert item['provenance']['synthetic'] is True
            assert set(SystemOneRequest(**item['request']).questions) == set(item['expected'])


def test_nonfinite_response_is_kept_as_explicit_invalid_value(tmp_path, capsys):
    from scripts.evaluate import main
    item = {'id': 'nan', 'request': {'state': 'x', 'questions': {'n': {'type': 'noul'}}}, 'expected': {'n': True}}
    data, raw, out = tmp_path / 'data.jsonl', tmp_path / 'raw.json', tmp_path / 'out.json'
    data.write_text(json.dumps(item) + '\n')
    raw.write_text(json.dumps({'results': [{'id': 'nan', 'response': {'answers': {'n': {'noul': float('nan')}}}}]}))
    assert main(['--data', str(data), '--responses', str(raw), '--out', str(out)]) == 1
    report = json.loads(out.read_text())
    assert report['summary']['errors'][0]['question'] == 'n'
    assert report['results'][0]['response']['answers']['n']['noul'] == {'invalid_nonfinite_number': 'nan'}
    capsys.readouterr()
