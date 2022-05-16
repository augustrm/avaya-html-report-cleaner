"""
Author: augustrm (https://github.com/augustrm)
Organization: Partnership Health Center

A script for untangling Avaya's phone reports.
Reports are generated as HTML documents containing a large number of <label>
objects that are arranged into a grid via absolute positions provided by inline CSS.
This presents a problem; mechanically, none of the relational data is actually linked.

We approach this issue by inferring relationships from enforcing an ordering over the CSS
absolute coordinates, e.g. each <label> at the same height can be considered to be in the
same row. From here a pandas dataframe is constructed and some basic cleanup is done.

EXTERNAL DEPENDENCIES::
- beautifulsoup4
- lxml
- numpy
- pandas
- sqlalchemy

->> pip install beautifulsoup4 lxml pandas numpy sqlalchemy

Build Environment: 
    Date: 2022-04-29
    OS: Windows 10 ; ver. 21H2
    Python Ver.: 3.10.2
    Python Source: https://www.python.org/downloads/release/python-3102/
    Python package manager: pip 21.2.4
    Editor: VScode

Style Notes:
    1.
        Comments '#' are subqualified with certain active characters ('?','!','*','//','todo') used by a VScode plugin
        called 'Better Comments' to facilitate richer specification
    2.
        Though not necessary to proper functionality, the entire script is wrapped in a 'main()' function.
        This function is invoked at the end of the file with a conditional check to test if the program is running
        in a standalone manner or as a sub-package to another script. If the script is run normally, all code is 
        interpreted and executed; if not, and the script is being imported, no code is executed and only static
        objects are available to the importing script, i.e. classes, functions, etc.
"""


def main(TARGET_FILE:str, useSQL:bool = False):
    if type(TARGET_FILE) != str:
        raise TypeError(f"TARGET_FILE must be str, given arg is {type(TARGET_FILE)}")
    elif type(useSQL) != bool:
        raise TypeError(f"useSQL must be bool, given arg is {type(useSQL)}")
        

    #! pkg imports
    #?-------------------------------------------------------------------------
    from bs4 import BeautifulSoup as bs
    from bs4 import UnicodeDammit
    import pandas as pd
    import numpy as np
    import re
    import datetime as dt
    
    #! non-anon function definitions
    #?-------------------------------------------------------------------------
    def css_to_dict(css_str):
        out_dict = {}
        _css_str = str(css_str)
        css_list = _css_str.split(sep="; ")
        for i in css_list:
            elet = i.split(':')
            #* trailing ";" in initial CSS generates a list containing an empty string, skip iteration if this is the case.
            if elet == ['']: 
                continue
            out_dict[elet[0]] = elet[1]    # "append" key-value pair to dict
        return out_dict

    def get_coordinates(css_dict):
        i_coord = int(css_dict["top"].replace("px","")) #row index
        j_coord = int(css_dict["left"].replace("px","")) #column index
        return (i_coord, j_coord)

    def get_index(css_str):
        return get_coordinates(css_to_dict(css_str))

    #! main runtime
    #?-------------------------------------------------------------------------
    with open(TARGET_FILE, "r") as f:
        phone_data = UnicodeDammit(f.read()).unicode_markup #force unicode.

    doc = bs(phone_data, "lxml")

    Label_elets = []
    for i in doc.find_all("label"):
        Label_elets.append(i)

    #? data points of the form [(col,row), "Data"] ::: col->int, row->int, "Data"->string.
    #? (col, row) pairs are scraped from the inline styling of each label tag
    #? It is beyond the author's comprehension as to WHY these data were not just packed in an HTML table in the first place.
    indexed_data = []
    _col_titles = []
    for i in Label_elets:
        if i.string == None:
            continue
        if css_to_dict(i["style"])["font"] == "bold 12px verdana":
            _col_titles.append(re.split(r'\|+', i.string.strip().replace(u'\xa0', u'|')))
        indexed_data.append([get_index(i["style"]), i.string.strip().replace(u'\xa0', u' ')]) #* .strip() call removes HTML &nbsp; (\xa0 in unicode)


    #? Handle Column titles being broken into multiple, fragmented rows
    #? See minor comments (#* ...) for some explanation of the dancing around we do here
    max_title_list_length = max(len(x) for x in _col_titles)
    col_titles = []
    for i in _col_titles:
        if i == ['']:
            continue
        elif len(i) < max_title_list_length: #* admittedly this is a fragile clause; it depends on there being more than a single maximum length list in _col_titles
            continue
        else:
            if len(col_titles) == 2: break #* break out of loop once we have first two instances, any more are redundant
            col_titles.append(i)

    zip_col_titles = zip(*col_titles) #* unpack nested list col_titles, then zip sublists together (element-wise tuple concat)
    final_col_titles = []
    for i in zip_col_titles:
        final_col_titles.append(" ".join(i)) #* join tuples resulting from zip into final strings
    final_col_titles.insert(0, "TIME") #* add Time title that isn't included in a "bold" styled <label>



    #? Get all unique ROW indices from each [(col,ROW), "data"]
    row_indices_set = set() #* We do a little trick and use a set object to guarantee uniqueness for free
    for i in indexed_data:
        row_indices_set.add(i[0][0])

    #? enforce ordering on row index values
    row_indices_list = list(row_indices_set)
    row_indices_list.sort()

    #? Take ordered row indices and retrieve all data points that fall in that row, adding them to matrix_dict
    #? matrix dict is of the form: 
    #? {row index i : [ [(i,col index j_1), "Data"],...,[(i,col index j_n), "Data"] ]} ::: i->int, j_k->int, "Data"->string
    #? i.e. it is a dict of lists of lists 
    matrix_dict = {}
    for i in row_indices_list:
        matrix_dict[i] = []
        for j in indexed_data:
            if j[0][0] == i:
                matrix_dict[i].append(j)


    #? Sub-sort column elements in each row entry of matrix_dict.
    #? We technically get total ordering of rows for free from the inherent structure
    #? of the HTML document, but I do not trust that to always be the case, so we force a total ordering.
    sorted_rows_dict = {}
    for i in matrix_dict.keys():
        row = []
        matrix_dict[i].sort(key=lambda x: x[0][1])
        for j in matrix_dict[i]:
            row.append(j[1])
        sorted_rows_dict[i] = row

    metadata_dict={}
    for _key,val in sorted_rows_dict.items():
        if len(val) == 1:
            if re.match(pattern = r'[A-z\s]+:(?![0-9])', string = val[0]) != None:
                datum = val[0].split(":")
                metadata_dict[datum[0].strip()] = datum[1].strip()
            continue
        for i in val:
            if re.match(pattern = r'[A-z\s]+:(?![0-9])', string = i) != None:
                metadata_dict[re.sub(r' +', r' ', i[:-1])] = re.sub(r' +', r' ',val[val.index(i)+1]) #* re.sub statements are to deal with extraneous whitespace
    
    #// TODO: fix "Date:" timestamps to be in unix standard time in metadata
    _timestamp = metadata_dict["Date"]
    fixed_timestamp = dt.datetime.strptime(_timestamp, "%I:%M %p %a %b %d, %Y")
    metadata_dict["Date"] = fixed_timestamp


    #? Construct final dataframe such that each key-value pair is a ROW
    df = pd.DataFrame.from_dict(sorted_rows_dict, orient='index')

    #* produce a deep copy of df, dropping rows whose 0th element contains letters
    #* use deep copy to avoid returning a view, which is non-deterministic 
    df1 = df[~df[0].str.contains("[a-zA-Z]").fillna(False)].copy(deep=True)

    df1[0].replace('',np.nan, inplace=True)
    df1[0].replace(r'--+',np.nan, inplace=True, regex=True)
    df1.dropna(subset=[0], inplace=True)
    df1[0].replace(r' +', '', inplace=True, regex=True)
    df1.columns = final_col_titles
    df1.reset_index(drop=True, inplace=True)

    #* prepend metadata columns for use with relational databases
    for k,v in metadata_dict.items():
        df1.insert(0, k, [v for _ in range(len(df1.index))])
    #df1.insert(0,"uuid", [uuid.uuid4() for _ in range(len(df1.index))]) #don't really need uuids, but good to have options


    #? Handle Data Export to target destination, dependent on argv "useSQL"
    #! for info on building your connection string, see SQLAlchemy docs: https://www.sqlalchemy.org/library.html#reference
    #! the below is written with MSSQL in mind, but can be easily adapted to use Postgres or mysql
    if useSQL == False:
        df1.to_csv(f"phone_data_{TARGET_FILE}.csv")
    else:
        import sqlalchemy
        server = 'YOUR SERVER HERE'
        database = 'YOUR DB HERE'
        mssql_conn_string = f"mssql+pyodbc://{server}/{database}" #* no credential spec for testing purposes; some variety of auth will be needed for full deployment

        engine = sqlalchemy.create_engine(mssql_conn_string, fast_executemany=True) #* Note the fast_executemany flag prebuffers all rows in RAM; DO NOT USE WITH LARGE DATA SETS
        with engine.connect() as connection:
            if 'Skill' in df1.columns:
                print('query to Skill table in mssql')
            if 'VDN' in df1.columns:
                print('query to VDN table in mssql')
            print('imagine a SQL transaction is happening here. It will look like df1.to_sql(name=\'target_table\', con=connection)')
        

    #? create exceptions for log testing
    #exception_generator = 1/0 #! I THROW EXCEPTIONS AND CAUSE PROBLEMS

    '''
    #! SQL connection testing::
        #! spec for SQLite3 mini-db
    table_name = "phone_data"
    conn = sqlite3.connect(f"{table_name}.sqlite")
    cur = conn.cursor()
    df2.to_sql(table_name, conn, if_exists='append', index=False)
    conn.close()


    conn1 =  sqlite3.connect(f"{table_name}.sqlite")
    cur1 = conn1.cursor()
    for i in cur1.execute(f"SELECT * FROM {table_name}"):
        print(i)
    conn1.close()
    '''

if __name__=="__main__":
    import logging
    import argparse

    parser = argparse.ArgumentParser(description="pseudo-ETL script for handling html Avaya phone system data")
    parser.add_argument('inputFile',
        nargs=1,
        help="pos. argument; reads in target .html file path as str"
    )
    parser.add_argument('-s', '--useSQL',
        dest='arg_useSQL',
        action='store_const',
        const=True,
        default=False,
        help="optional flag that determines whether the output is sent to a SQL server or to a flat file; defaults to False -> (creates flat file)"
    )

    #args = parser.parse_args(["phone_data.html", "--useSQL"]) #! simulated shell arguments for debugging
    args = parser.parse_args()

    logging.basicConfig(filename="phone_data_cleaner.log", filemode='a',level=logging.INFO, format='-----------------\n%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    file_in, _useSQL = args.inputFile[0] , args.arg_useSQL

    try:
        print(file_in, _useSQL)
        logging.info(f"Given shell arguments: inputFile: {file_in}, useSQL: {_useSQL}")
        
        #! main entry point:
        main(TARGET_FILE=file_in, useSQL=_useSQL)

    except Exception as e:
        logging.critical("Exception Occured", exc_info=True)
