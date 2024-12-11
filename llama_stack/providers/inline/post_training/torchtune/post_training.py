# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.
from llama_stack.apis.datasetio import DatasetIO
from llama_stack.providers.inline.post_training.torchtune.config import (
    TorchtunePostTrainingConfig,
)
from llama_stack.apis.post_training import *  # noqa
from llama_stack.providers.inline.post_training.torchtune.recipes.lora_finetuning_single_device import (
    LoraFinetuningSingleDevice,
)


class TorchtunePostTrainingImpl:
    def __init__(
        self,
        config: TorchtunePostTrainingConfig,
        datasetio_api: DatasetIO,
        datasets: Datasets,
    ) -> None:
        self.config = config
        self.datasetio_api = datasetio_api
        self.datasets_api = datasets

    async def supervised_fine_tune(
        self,
        job_uuid: str,
        training_config: TrainingConfig,
        hyperparam_search_config: Dict[str, Any],
        logger_config: Dict[str, Any],
        model: str,
        checkpoint_dir: Optional[str],
        algorithm_config: Optional[Union[LoraFinetuningConfig, QATFinetuningConfig]],
    ) -> PostTrainingJob:
        if isinstance(algorithm_config, LoraFinetuningConfig):
            recipe = LoraFinetuningSingleDevice(
                self.config,
                training_config,
                hyperparam_search_config,
                logger_config,
                model,
                checkpoint_dir,
                algorithm_config,
                self.datasetio_api,
                self.datasets_api,
            )
            await recipe.setup()
            await recipe.train()
        else:
            raise NotImplementedError()

        return PostTrainingJob(job_uuid=job_uuid)

    async def preference_optimize(
        self,
        job_uuid: str,
        finetuned_model: str,
        algorithm_config: DPOAlignmentConfig,
        training_config: TrainingConfig,
        hyperparam_search_config: Dict[str, Any],
        logger_config: Dict[str, Any],
    ) -> PostTrainingJob: ...

    # TODO @SLR722 impelment below APIs
    async def get_training_jobs(self) -> List[PostTrainingJob]: ...

    # sends SSE stream of logs
    @webmethod(route="/post-training/job/logs")
    async def get_training_job_logstream(
        self, job_uuid: str
    ) -> PostTrainingJobLogStream: ...

    @webmethod(route="/post-training/job/status")
    async def get_training_job_status(
        self, job_uuid: str
    ) -> PostTrainingJobStatusResponse: ...

    @webmethod(route="/post-training/job/cancel")
    async def cancel_training_job(self, job_uuid: str) -> None: ...

    @webmethod(route="/post-training/job/artifacts")
    async def get_training_job_artifacts(
        self, job_uuid: str
    ) -> PostTrainingJobArtifactsResponse: ...
