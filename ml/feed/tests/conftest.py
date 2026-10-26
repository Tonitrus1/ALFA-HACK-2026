from pathlib import Path
import os

import pytest

from ml.feed.catalog import Catalog
from ml.feed.integration import make_request


def pytest_addoption(parser):
    parser.addoption('--with-model', action='store_true', help='Require prepared real E5 bundle')


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
    from ml.feed.ranker import ModelRanker
    return ModelRanker(catalog, Path(os.environ.get('FEED_BUNDLE', '.local/feed-bundle')))
