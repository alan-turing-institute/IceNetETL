# Third party
import pandas as pd


class InputBlobTriggerException(Exception):
    pass


def batches(input, size):
    """Yield successive chunks of up to 'size' elements from input."""
    if isinstance(input, pd.DataFrame):
        output = []
        for tuple_ in input.itertuples(False):
            output.append(tuple_)
            if len(output) >= size:
                yield output
                output = []
        if output:
            yield output
            output = []
    else:
        for idx in range(0, len(input), size):
            yield input[idx : idx + size]


def human_readable(seconds):
    """Human readable string from seconds"""
    days, seconds = divmod(int(seconds), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return f"{days:d}d{hours:d}h{minutes:d}m{seconds:d}s"
    if hours > 0:
        return f"{hours:d}h{minutes:d}m{seconds:d}s"
    if minutes > 0:
        return f"{minutes:d}m{seconds:d}s"
    return f"{seconds:d}s"


def mean_step_size(input_):
    return (max(input_) - min(input_)) / (len(input_) - 1)
