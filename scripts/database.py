import pandas as pd


def fetch_data_base(file_name, bonus=False):
    df_cells = pd.read_csv(file_name)
    if not bonus:
        df_cells = df_cells.loc[df_cells["Type"] == "Essential"]
    return df_cells.set_index("Cell Name")
