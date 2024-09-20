# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

from enum import Enum
from typing import Any, Dict, Protocol

from llama_models.schema_utils import json_schema_type, webmethod
from pydantic import BaseModel

from llama_models.llama3.api.datatypes import *  # noqa: F403


@json_schema_type
class ViolationLevel(Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@json_schema_type
class SafetyViolation(BaseModel):
    violation_level: ViolationLevel

    # what message should you convey to the user
    user_message: Optional[str] = None

    # additional metadata (including specific violation codes) more for
    # debugging, telemetry
    metadata: Dict[str, Any] = Field(default_factory=dict)


@json_schema_type
class RunShieldResponse(BaseModel):
    violation: Optional[SafetyViolation] = None


class Safety(Protocol):
    @webmethod(route="/safety/run_shield")
    async def run_shield(
        self, shield: str, messages: List[Message], params: Dict[str, Any] = None
    ) -> RunShieldResponse: ...
