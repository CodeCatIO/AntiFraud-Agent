#导入库
import pandas as pd
from sklearn.discriminant_analysis import StandardScaler
from sklearn.impute import KNNImputer,SimpleImputer


def fill_missing_values(data):
    if 'label' in data.columns:
        data = data.drop('label', axis=1)
    '''
    小于100用0填充
    大于100小于500用均值填充
    大于500用k近邻填充
    '''
    if len(data) < 100:
        data = data.fillna(0)
    elif len(data) >= 100 and len(data) < 500:
        imputer = SimpleImputer(strategy='mean')
        data_filled = imputer.fit_transform(data)
        data = pd.DataFrame(data_filled, columns=data.columns, index=data.index)
    else:
        imputer = KNNImputer(n_neighbors=42, weights='distance')
        data_filled = imputer.fit_transform(data)
        data = pd.DataFrame(data_filled, columns=data.columns, index=data.index)
    return data


#数据标准化
def scale_data(data):
    # 进行数据标准化
    scaler = StandardScaler()
    data = pd.DataFrame(scaler.fit_transform(data), columns=data.columns)
    #data.to_csv('output.csv', index=True)
    return data
