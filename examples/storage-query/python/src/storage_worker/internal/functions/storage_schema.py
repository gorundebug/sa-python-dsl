"""Native SQLAlchemy description, never automatically applied at startup."""
from sqlalchemy import Column, LargeBinary, MetaData, Table, Text

items = Table("query_example_items", MetaData(),
              Column("key", Text, primary_key=True),
              Column("value", LargeBinary, nullable=False))
