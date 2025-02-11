import re

def _run_regex_and_extract_value(pattern, source):
    res = re.search(pattern, source, re.IGNORECASE)
    if res is not None:
        return res.groups()[0]
    else:
        return None

def discover_loot(address, output):
    
    loot_discovered = []
    for line in output.split("\n"):
        #Log.logger.debug("Reviewing line %s" % line)
        mssql_provider = _run_regex_and_extract_value("PROVIDER=(\w+)" ,line)
        mssql_source   = _run_regex_and_extract_value("SOURCE=(\w+)"   ,line)
        mssql_user_id  = _run_regex_and_extract_value("USER ID=(\w+)"  ,line)
        mssql_pwd      = _run_regex_and_extract_value("PWD=(\w+)"      ,line)

        if mssql_provider is not None and mssql_source is not None and mssql_user_id is not None and mssql_pwd is not None:
            loot = {
                "provider":   mssql_provider,
                "source":     mssql_source,
                "username":   mssql_user_id,
                "password":   mssql_pwd,
                "loot_type":  "credentials",
                "loot_space": "mssql",
                "address":    address,
            }
            loot_discovered.append(loot)
            #Log.logger.debug(loot)

    return loot_discovered

def get_files_list_from_output(files_lines):
    files_list = []

    # WE SHOULD TRY TO FIND OUT THE OPERATING SYSTEM OR TYPE OF LISTING

    for line in files_lines:
        filename = " ".join(line.split()[5:])
        filesize = " ".join(line.split()[0:2])
        files_list.append({
            "filename": filename,
            "filesize": filesize,
        })

    return files_list
