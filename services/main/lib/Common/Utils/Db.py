from mysql.connector import DatabaseError
import mysql.connector
import types
import lib.Common.Utils.Constants as Constants
import time
import traceback

class Db:
    def __init__(self, db_name, db_password, db_host, logger=None):
        self.db_password = db_password
        self.db_name     = db_name
        self.db_user     = "root"
        self.db_host     = db_host
        self.logger      = logger

        print("Connecting with user %s password %s host %s db_name %s" % (self.db_user, self.db_password, self.db_host, self.db_name) )
        self.cnx    = mysql.connector.connect(user=self.db_user, password=self.db_password, host=self.db_host, database=self.db_name, port=Constants.DRAGON_DB_PORT)
        print("connected at port 6612")
        self.cursor = self.cnx.cursor() #prepared=True

        self.settings_cache = {}

    def get_cnx(self):
        try:
            self.cnx = self.cnx
        except:
            self.renew_connection_and_cursor()
        return self.cnx

    def renew_connection_and_cursor(self):
        self.cnx = mysql.connector.connect(user=self.db_user, password=self.db_password, host=self.db_host, database=self.db_name, port=Constants.DRAGON_DB_PORT)
        self.cursor = self.get_cnx().cursor()

    def get_cursor_last_row_id(self):
        try:
            lastrow_id = self.cursor.lastrowid
        except:
            self.renew_connection_and_cursor()
            lastrow_id = self.cursor.lastrowid
        return lastrow_id

    def execute(self,stmt, data = {}):
        MAX_ATTEMPTS = 1
        attempts     = 0
        while True:
            try:
                self.simple_execute(stmt,data)
                self.get_cnx().commit()
                lastrow_id = self.get_cursor_last_row_id()
                return lastrow_id
            except DatabaseError as e:
                err_code = e.args[0]
                if err_code == 1205:
                    if attempts < MAX_ATTEMPTS:
                        print("Error %s, we will retry in 5 seconds.." % traceback.format_exc())
                        time.sleep(5)
                        attempts += 1
                    else:
                        raise
                else:
                    raise

    def simple_execute(self, stmt, data = {}):
            self.cursor_execute(stmt,data)

    def execute_many(self, stmt, data_array):
        self.cursor_executemany(stmt, data_array)
        self.get_cnx().commit()

    def cursor_executemany(self, stmt, data):
        try:
            self.cursor.executemany(stmt, data)
        except:
            self.renew_connection_and_cursor()
            self.cursor.executemany(stmt, data)

    def insert(self, table, data):
        (stmt, interpolation_values) = self.prepare_insert_statement(table, data)
        response_id = self.execute(stmt,interpolation_values)
        return response_id

    """
    db.insert_or_update('service_status', ['account_id', 'service_name', 'container_name', 'health_status'], container_data )
    """
    def insert_or_update(self, table, primary_keys, data):
        where_map = {}
        for key in primary_keys:
            where_map[key] = data[key]

        res = self.search_where(table, {'where': where_map} )
        if len(res):
            self.update_where(table, where_map, data)
        else:
            self.insert(table, data)

    """
    db.update_where('account', {'account_id':account.account_id}, {'new':1} )
    """
    def update_where(self, table, where_map, data):
        (where, query_data) = self._create_where_from_data(where_map)

        updates = []
        values  = []
        for key in data:
            update_key = "%s=" % key + '%s'
            updates.append(update_key)
            values.append(str(data[key]))

        update_str = ",".join(updates)
        statement  = "UPDATE %s SET %s %s" % (table, update_str, where)
        for dat in query_data:
            values.append(dat)

        self.execute(statement, values)

    def prepare_insert_statement(self, table, data):
        interpolation_values = []
        param_list = interpolation_list = ""
        for param in data:
            if param_list != "":
                param_list += ","
                interpolation_list += ","
            param_list += "%s" % param
            interpolation_list += '%s'
            interpolation_values.append(data[param])

        stmt = "INSERT INTO %s(%s) VALUES (%s)" % (table, param_list, interpolation_list)
        return stmt, interpolation_values

    def bulk_insert(self, table, inserts_array):
        (stmt, all_values) = ("",[])
        for data in inserts_array:
            (stmt, values) = self.prepare_insert_statement(table, data)
            all_values.append(values)
        self.execute_many(stmt,all_values)

    def _create_columns_from_data(self, columns):
        return ",".join(columns)

    def search_where_one(self, table, data = None):
        results = self.search_where(table, data)
        if len(results) > 0:
            return results[0]

        return None

    def clean_test_database(self):
        if not self.db_name.endswith("_test"):
            raise ValueError(f"This method can only be run on test databases, not on {self.db_name}")
        else:
            self.logger.warning(f"Truncating all tables in db {self.db_name}")
            results = self.query("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE!=\"VIEW\"", (self.db_name, ))
            for result in results:
                table_name = result['TABLE_NAME']
                # self.logger.debug(f"Truncating table {table_name}")
                self.execute(f"TRUNCATE {table_name}")

        return True

# SEARCH WHERE
    #db.search_where('accounts', { 'where': { 'account_id': account_id, 'siem_token': token } } )
    def search_where(self, table, data = None):
        where      = ""
        order_by   = ""
        limit      = ""
        columns    = "*"
        query_data = ()

        if data is not None:
            if 'WHERE' not in data and 'where' not in data and 'FULL_SCAN' not in data:
                raise ValueError("You need a where unless you want a full scan")

            if 'where' in data:
                (where, query_data) = self._create_where_from_data(data['where'])
            elif 'WHERE' in data:
                (where, query_data) = self._create_where_from_data(data['WHERE'])

            if 'columns' in data:
                columns = self._create_columns_from_data(data['columns'])
            elif 'COLUMNS' in data:
                columns = self._create_columns_from_data(data['COLUMNS'])

            if 'order_by' in data:
                order_by += " ORDER BY %s" % data['order_by']
            elif 'ORDER_BY' in data:
                order_by += " ORDER BY %s" % data['ORDER_BY']

            if 'limit' in data:
                limit += " LIMIT %s" % data['limit']
            elif 'LIMIT' in data:
                limit += " LIMIT %s" % data['LIMIT']


        stmt = "SELECT %s FROM %s %s %s %s" % (columns, table, where, order_by, limit)
        results = self.fetch(stmt, query_data)
        return results

    def query(self, stmt, query_data = ()):
        #stmt = "SELECT %s FROM %s %s %s %s" % (columns, table, where, order_by, limit)
        results = self.fetch(stmt, query_data)
        return results

    def _create_where_from_data(self, data):
        where = ""
        where_data = []
        if data is not None:
            for key in data:
                value = data[key]
                if where == "":
                    where = "WHERE "
                else:
                    where += " AND "

                if type(value) in types.StringTypes:
                    where +=  "%s=" % key + '%s'
                    where_data.append(value)
                elif type(value) == types.IntType or type(value) == types.LongType:
                    where +=  "%s=" % key + '%s'
                    where_data.append(value)
                else:
                    if key == "OR":
                        or_query = ""
                        for or_key in value:
                            if or_query != "":
                                or_query += " OR "
                            or_query +=  "%s like " % or_key + '%s'
                            where_data.append(value[or_key])
                        where += "(%s)" % or_query
                    else:
                        for comp_key in value:
                            where +=  "%s%s" % (key, comp_key) + '%s'
                            where_data.append(value[comp_key])

        #print (where, where_data)
        return where, where_data
	#! SEARCH WHERE

    def cursor_execute(self, stmt, data):
        try:
            self.cursor.execute(stmt, data)
        except:
            self.renew_connection_and_cursor()
            self.cursor.execute(stmt, data)

    def get_cursor_description(self):
        try:
            return self.cursor.description
        except:
            self.renew_connection_and_cursor()
            return self.cursor.description

    def get_cursor_fetch_all(self):
        try:
            return self.cursor.fetchall()
        except:
            self.renew_connection_and_cursor()
            return self.cursor.fetchall()

    def fetch(self, stmt, data = () ):
        # Log.logger.debug([stmt, data])

        self.cursor_execute(stmt, data)
        columns = self.get_cursor_description()
        results = [{columns[index][0]:column for index, column in enumerate(value)} for value in self.get_cursor_fetch_all()]
        self.get_cnx().commit()
        return results

    def close(self):
        self.cursor.close()
        self.get_cnx().close()

    def __exit__(self, exc_type, exc_value, traceback):
        self.cursor.close()