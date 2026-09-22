"""The gallery contains bilingual, runnable inputs, never prefilled model answers."""
import json
from pathlib import Path

import pytest

from openjev.engine import make_pairs
from openjev.schema import SystemOneRequest

EXAMPLES = json.loads(Path('openjev/examples.json').read_text())
EXISTING_IDS = ['support', 'chinese', 'review', 'facts', 'product_quality']
NEW_IDS = ['feedback', 'content', 'intake', 'service', 'meeting', 'delivery', 'policy']
ALLOWED_ICONS = {'ticket', 'globe', 'star', 'check', 'book', 'sliders', 'history', 'code', 'branches', 'chart', 'info', 'lock'}


def test_gallery_keeps_existing_links_and_exposes_twelve_unique_examples():
    ids = [example['id'] for example in EXAMPLES]
    assert ids == EXISTING_IDS + NEW_IDS
    assert len(ids) == len(set(ids)) == 12


@pytest.mark.parametrize('example', EXAMPLES, ids=lambda example: example['id'])
def test_bilingual_request_shapes_and_candidate_order_match(example):
    english = SystemOneRequest(state=example['state'], questions=example['questions'])
    chinese = SystemOneRequest(state=example['state_zh'], questions=example['questions_zh'])
    assert type(english.state) is type(chinese.state)
    # State object labels may be translated, but their value structure is retained.
    if isinstance(english.state, dict):
        assert [type(value) for value in english.state.values()] == [type(value) for value in chinese.state.values()]
    assert list(english.questions) == list(chinese.questions)
    assert len(english.questions) == 3
    for identifier, question in english.questions.items():
        translated = chinese.questions[identifier]
        assert question.type == translated.type
        assert set(example['questions'][identifier]) == set(example['questions_zh'][identifier])
        assert question.instructions and translated.instructions
        if question.type == 'choice':
            assert list(question.criteria) == list(translated.criteria)
            assert all(value for value in question.criteria.values())
            assert all(value for value in translated.criteria.values())
        elif question.type == 'score':
            assert len(question.criteria) == len(translated.criteria)
        else:
            assert question.criteria == translated.criteria


@pytest.mark.parametrize('example', EXAMPLES, ids=lambda example: example['id'])
def test_examples_have_bilingual_gallery_metadata_and_fictional_input(example):
    for field in ('name', 'description', 'category', 'learning'):
        assert isinstance(example[field], str) and example[field].strip()
        assert isinstance(example[field + '_zh'], str) and example[field + '_zh'].strip()
        assert example[field] != example[field + '_zh']
    assert example['icon'] in ALLOWED_ICONS
    if isinstance(example['state'], str):
        assert example['state'].lower().startswith('fictional')
        assert '虚构' in example['state_zh']
    else:
        assert example['state']['fictional'] is True
        assert example['state_zh']['演示数据'] is True


def test_shared_gallery_categories_have_consistent_translations():
    translations = {}
    for example in EXAMPLES:
        previous = translations.setdefault(example['category'], example['category_zh'])
        assert previous == example['category_zh']


@pytest.mark.parametrize('example', EXAMPLES, ids=lambda example: example['id'])
def test_gallery_payloads_are_inputs_without_prefilled_predictions(example):
    allowed = {'id', 'name', 'name_zh', 'description', 'description_zh', 'state', 'state_zh',
               'questions', 'questions_zh', 'icon', 'category', 'category_zh', 'learning', 'learning_zh'}
    assert set(example) == allowed
    for variant in ('questions', 'questions_zh'):
        for question in example[variant].values():
            assert set(question) <= {'type', 'instructions', 'criteria'}


def test_existing_question_ids_types_and_choice_keys_remain_compatible():
    expected = {
        'support': [('department', 'choice', ['technical', 'billing', 'sales']), ('frustration', 'score', 3), ('is_urgent', 'noul', None)],
        'chinese': [('intent', 'choice', ['refund', 'purchase', 'shipping']), ('sentiment', 'score', 3), ('defective', 'noul', None)],
        'review': [('sentiment', 'choice', ['positive', 'neutral', 'negative']), ('satisfaction', 'score', 4), ('recommends', 'noul', None)],
        'facts': [('delivered', 'noul', None), ('in_london', 'noul', None), ('likes_color', 'noul', None)],
        'product_quality': [('consistency', 'choice', ['consistent', 'conflicting', 'insufficient']), ('completeness', 'score', 4), ('missing_care_instructions', 'noul', None)],
    }
    for example in EXAMPLES[:5]:
        actual = []
        for identifier, question in example['questions'].items():
            criteria = question.get('criteria')
            signature = list(criteria) if isinstance(criteria, dict) else len(criteria) if isinstance(criteria, list) else None
            actual.append((identifier, question['type'], signature))
        assert actual == expected[example['id']]


@pytest.mark.parametrize('example', EXAMPLES[5:], ids=lambda example: example['id'])
def test_new_examples_cover_all_primitives_with_four_concrete_score_levels(example):
    for variant in ('questions', 'questions_zh'):
        questions = list(example[variant].values())
        assert sorted(question['type'] for question in questions) == ['choice', 'noul', 'score']
        levels = next(question['criteria'] for question in questions if question['type'] == 'score')
        assert len(levels) == len(set(levels)) == 4
        assert all(level.strip() for level in levels)


def test_policy_keeps_unknown_evidence_as_a_separate_choice():
    policy = next(example for example in EXAMPLES if example['id'] == 'policy')
    for variant in ('questions', 'questions_zh'):
        evidence = policy[variant]['rule_evidence']
        assert evidence['type'] == 'choice'
        assert list(evidence['criteria']) == ['supported', 'contradicted', 'insufficient_information']


@pytest.mark.parametrize('example', EXAMPLES, ids=lambda example: example['id'])
def test_gallery_inputs_stay_short_and_build_valid_candidate_pairs(example):
    # This is a text-size regression check, not a tokenizer or accuracy claim.
    # The pinned local CPU tokenizer is checked separately without loading weights.
    for suffix in ('', '_zh'):
        request = SystemOneRequest(state=example['state' + suffix], questions=example['questions' + suffix])
        pairs, slices = make_pairs(request)
        assert len(slices) == 3
        assert 3 <= len(pairs) <= 10
        assert all(premise and hypothesis for premise, hypothesis in pairs)
        assert max(len(premise) + len(hypothesis) for premise, hypothesis in pairs) <= 1000
