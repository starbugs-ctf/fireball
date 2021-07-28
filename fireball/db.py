import databases
import sqlalchemy
from pydantic import BaseModel

from .config import DATABASE_URL

database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()


class Execution(BaseModel):
    id: int


class ExecutionIn(BaseModel):
    pass


executions = sqlalchemy.Table(
    "executions",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
)

engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
metadata.create_all(engine)
