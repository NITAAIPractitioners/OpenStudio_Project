import openstudio
import pandas as pd


sql = openstudio.SqlFile("eplusout.sql")

for env in sql.availableEnvPeriods():
    print("Environment:", env)

    # Get start and end date
    start = sql.environmentPeriodStartDate(env)
    end = sql.environmentPeriodEndDate(env)

    if start.is_initialized() and end.is_initialized():
        print("Start Date:", start.get())
        print("End Date:", end.get())