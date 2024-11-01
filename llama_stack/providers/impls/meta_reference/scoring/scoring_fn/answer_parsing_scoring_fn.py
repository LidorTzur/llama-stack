# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.
import re

from .base_scoring_fn import BaseScoringFn
from llama_stack.apis.scoring_functions import *  # noqa: F401, F403
from llama_stack.apis.scoring import *  # noqa: F401, F403
from llama_stack.apis.common.type_system import *  # noqa: F403
from .common import aggregate_accuracy

from .fn_defs.answer_parsing_multiple_choice import answer_parsing_multiple_choice


class AnswerParsingScoringFn(BaseScoringFn):
    """
    A scoring_fn that parses answer from generated response according to context and check match with expected_answer.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.supported_fn_defs_registry = {
            answer_parsing_multiple_choice.identifier: answer_parsing_multiple_choice,
        }

    async def score_row(
        self,
        input_row: Dict[str, Any],
        scoring_fn_identifier: Optional[str] = None,
    ) -> ScoringResultRow:
        assert (
            scoring_fn_identifier is not None
        ), "Scoring function identifier not found."
        fn_def = self.supported_fn_defs_registry[scoring_fn_identifier]
        assert (
            fn_def.context is not None
            and fn_def.context.type == ScoringContextType.answer_parsing.value
        ), f"AnswerParsingContext not found for {fn_def}."

        expected_answer = input_row["expected_answer"]
        generated_answer = input_row["generated_answer"]

        # parse answer according to regex
        parsed_answer = None
        for regex in fn_def.context.parsing_regex:
            match = re.search(regex, generated_answer)
            if match:
                parsed_answer = match.group(1)
                break

        score = 1.0 if parsed_answer and parsed_answer == expected_answer else 0.0
        return {
            "score": score,
        }

    async def aggregate(
        self,
        scoring_results: List[ScoringResultRow],
        scoring_fn_identifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        return aggregate_accuracy(scoring_results)
