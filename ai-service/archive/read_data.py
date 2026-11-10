import pandas as pd

# 读取数据
def read_data(train_file_path, val_file_path=None):
    df_train = pd.read_csv(train_file_path, index_col="sample_id")
    if 'label' in df_train.columns:
        y_train = df_train['label'].copy()
    else:
        y_train = None
    if val_file_path:
        df_val = pd.read_csv(val_file_path, index_col="sample_id")
        if 'label' in df_val.columns:
            y_val = df_val['label'].copy()
        else:
            y_val = None
        return df_train, y_train, df_val, y_val
    else:
        return df_train, y_train

#删除重复值
def remove_duplicates(data, y):
    data = data.drop_duplicates()
    y = y.loc[data.index]
    return data, y

#删除无用特征列
def drop_features(data):
    features_to_drop = ['feature57', 'feature77', 'feature100', 'feature92', 'feature88', 'feature65', 'feature54'
                        , 'feature80', 'feature1', 'feature60', 'feature32', 'feature78', 'feature20'] # 在这里定义要删除的特征名称列表
    data = data.drop(features_to_drop, axis=1)
    return data