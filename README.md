# Avaya HTML report cleaner
A script for untangling Avaya phone server's HTML reports to be properly machine readable.

Developed for [Partnership Health Center](https://www.partnershiphealthcenter.org/) in Missoula, MT 


EXTERNAL PYTHON DEPENDENCIES:
- beautifulsoup4
- lxml
- numpy
- pandas
- sqlalchemy

<code>pip install beautifulsoup4 lxml pandas numpy sqlalchemy</code>


## About
Reports are generated as HTML documents containing a large number of <label>
objects that are arranged into a grid via absolute positions provided by inline CSS.
This presents a problem; mechanically, none of the relational data is actually linked.

We approach this issue by inferring relationships from enforcing an ordering over the CSS
absolute coordinates, e.g. each <label> at the same height can be considered to be in the
same row. From here a pandas dataframe is constructed and some basic cleanup is done.
