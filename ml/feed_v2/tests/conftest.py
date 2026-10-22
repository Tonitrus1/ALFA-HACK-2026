from pathlib import Path

import pytest

from ml.feed_v2.catalog import Catalog
from ml.feed_v2.integration import make_request


def pytest_addoption(parser):
    parser.addoption('--with-model', action='store_true', help='Require prepared real E5 bundle')
    parser.addoption('--with-learned', action='store_true', help='Require trained CatBoost bundle')


@pytest.fixture(scope='session')
def catalog():
    return Catalog()


@pytest.fixture
def request_body(catalog):
    return make_request(catalog, request_id='rank-test', exposure_id='ex-test',
                        candidate_ids=sorted(catalog.cards),
                        profile={'task': 'PURCHASE', 'help': 'COST', 'depth': 'EXPLAINED'})


@pytest.fixture(scope='session')
def real_model(request, catalog):
    if not request.config.getoption('--with-model'):
        pytest.skip('Use --with-model to require real offline E5')
    from ml.feed_v2.ranker import ModelRanker
    import os
    return ModelRanker(catalog, Path(os.environ.get('FEED_V2_TEST_BUNDLE','.local/feed-v2-acceptance/e5')))


@pytest.fixture(scope='session')
def learned_model(request, catalog):
    if not request.config.getoption('--with-learned'):
        pytest.skip('Use --with-learned to require a trained offline bundle')
    import os
    from ml.feed_v2.learned import LearnedRanker
    return LearnedRanker(catalog, Path(os.environ.get('FEED_LEARNED_TEST_BUNDLE', '.local/feed-catboost')))
