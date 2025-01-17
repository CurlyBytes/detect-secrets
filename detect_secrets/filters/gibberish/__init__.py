import os
import string
from functools import lru_cache
from typing import Any
from typing import Optional

from ...core.plugins import Plugin
from ...plugins.private_key import PrivateKeyDetector
from ...settings import get_settings
from ..util import compute_file_hash


Model = Any


def is_feature_enabled() -> bool:
    try:
        get_model()
        return True
    except ImportError:
        return False


def initialize(model_path: Optional[str] = None, limit: float = 3.7) -> None:
    """
    :param limit: this limit was obtained through trial and error. Check out
        the original pull request for rationale.

    :raises: ValueError
    """
    path = model_path
    if not path:
        path = os.path.join(__path__[0], 'rfc.model')

    model = get_model()

    from gibberish_detector import serializer
    from gibberish_detector.exceptions import ParsingError
    with open(path) as f:
        try:
            model.update(serializer.deserialize(f.read()))
        except ParsingError:
            raise ValueError('Invalid model.')

    config = {
        'limit': limit,
    }
    if model_path:
        config['model'] = model_path
        config['file_hash'] = compute_file_hash(model_path)

    path = f'{__name__}.should_exclude_secret'
    get_settings().filters[path] = config


def should_exclude_secret(secret: str, plugin: Optional[Plugin] = None) -> bool:
    """
    :param plugin: optional, for easier testing. The dependency injection system
        will populate its proper value on complete runs.
    """
    # Private keys are actual words, so they will be a false negative.
    if isinstance(plugin, PrivateKeyDetector):
        return False

    # Through real-life experimentation, we discovered that the gibberish detector
    # works best with non-hex strings, since hex strings have a too limited charset
    # to fit our trained models. As such, we cannot make a deterministic decision
    # in such cases.
    if not (set(secret) - set(string.hexdigits + '-')):
        return False

    if not get_model().data or not get_model().charset:
        raise AssertionError('Attempting to use uninitialized gibberish model.')

    from gibberish_detector.detector import Detector
    detector = Detector(
        model=get_model(),
        threshold=get_settings().filters[f'{__name__}.should_exclude_secret']['limit'],
    )

    # TODO: secret.lower() is only used currently, since the default model is only
    # trained with lower case letters. However, in the future, if people want to train
    # a model that is case-sensitive, we can figure out how to change this.
    # Unfortunately, it's not straight-forward to just remove the `.lower()` function call,
    # since if the string is *not* lowered (and the model expects it to be), the results
    # will be quite different.
    return not detector.is_gibberish(secret.lower())


@lru_cache(maxsize=1)
def get_model() -> 'Model':
    from gibberish_detector.model import Model
    return Model(charset='')
