import lib.Common.Utils.Log as Log

def load_agent_options(staging_connection, attributes=None):
    config = {}

    query_stmt = "SELECT attribute,value,attribute_type FROM agent_config" # MOVE TO AGENT COMMS

    if attributes is not None:
        query_stmt += " WHERE attribute IN ('%s')" % "','".join(attributes)
    # Log.logger.debug(query_stmt)

    results = staging_connection.query(query_stmt)
    for result in results:
        attribute = result["attribute"]
        config[attribute] = result["value"]
        if result['attribute_type'] == "INT":
            config[attribute] = int(config[attribute])
        elif result['attribute_type'] == "FLOAT":
            config[attribute] = float(config[attribute])
        elif result['attribute_type'] == "BOOL":
            if config[attribute] == "TRUE":
                config[attribute] = True
            elif config[attribute] == "FALSE":
                config[attribute] = False
            else:
                raise ValueError(f"BOOL values can either be TRUE or FALSE, provided was {config[attribute]}")

    # Log.logger.debug(config)
    return config
