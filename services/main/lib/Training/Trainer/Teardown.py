import lib.Training.Trainer.Preparation as Preparation
import lib.Training.Trainer.Setup as Setup
import lib.Common.Utils.Log             as Log
from   lib.Training.Trainer.Common import prune_containers

def teardown(staging_connection, remove=True):
    Log.add_info_large_ascii("TEARDOWN")
    Preparation.stop_agents(staging_connection)
    Preparation.stop_all_containers(remove=remove)
    Setup.teardown_castle()
    # prune_containers()
    if Log.logger is not None:
        Log.close_log()
    print("Finished tearing down training")
