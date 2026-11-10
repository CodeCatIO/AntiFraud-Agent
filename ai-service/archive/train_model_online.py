from read_data import read_data,remove_duplicates,drop_features
from missing_scale import fill_missing_values,scale_data
from keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.utils import compute_class_weight
from keras.regularizers import l1,l2
from sklearn.metrics import classification_report
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
import numpy as np
import datetime
import sys

#在此接收传入的文件地址
'''
*************你需要删除14到19行这是我的文件地址,你需要在运行此py前定义(在你的代码文件中定义，参数是共享的对吧)****************
'''
input_train_filepath = sys.argv[1]
#input_val_filepath = r'E:\code\jupyter\3xia\A10_HOBO\data\validate_1000.csv'

#input_train_filepath是传入的训练用的训练集文件地址.
#input_train_filepath是一定有的，但是input_val_filepath(训练用的验证集）可以没有
input_file_paths = [input_train_filepath]
if 'input_val_filepath' in locals():
    input_file_paths.append(input_val_filepath)


#如果input_file_paths里文件有两个则会分别赋值给两个变量，一个则只会赋值给train_model_online_file_path
if len(input_file_paths) == 2:
    train_model_online_file_path, val_model_online_file_path = input_file_paths
else:
    train_model_online_file_path = input_file_paths[0]


#以下是对数据集进行的操作
try:
    data = read_data(train_model_online_file_path, val_model_online_file_path)
except NameError:
    data = read_data(train_model_online_file_path)

if len(data) == 4:
    df_train, y_train, df_val, y_val = data
    df_train, y_train = remove_duplicates(df_train, y_train)
    df_val = drop_features(df_val)
    df_val = fill_missing_values(df_val)
    df_val = scale_data(df_val)
else:
    df_train, y_train = data

df_train = drop_features(df_train)
df_train = fill_missing_values(df_train)
df_train = scale_data(df_train)
#到此结束 下面是模型的训练



#模型构建及训练
def train_model_online(X_train, y_train, X_val = None, y_val = None):

    if X_val is  None or y_val is  None:
        X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.2)
        
    # 计算类别权重
    class_weights = compute_class_weight(class_weight='balanced',classes= np.unique(y_train),y= y_train)
    class_weights = dict(enumerate(class_weights))
    
    # 构建模型
    model = Sequential()
    model.add(Dense(94, activation='tanh', input_shape=(X_train.shape[1],), kernel_regularizer=l1(0.01)))
    model.add(Dense(282, activation='tanh',kernel_regularizer=l2(0.01)))
    model.add(Dense(252, activation='tanh',kernel_regularizer=l2(0.01)))
    model.add(Dense(42, activation='tanh',kernel_regularizer=l2(0.01)))
    model.add(Dense(6, activation='softmax'))
    
    # 编译模型
    model.compile(loss='categorical_crossentropy', optimizer='Adamax', metrics=['accuracy'])

    # 将标签数据转换为独热编码
    y_train = to_categorical(y_train)
    y_val = to_categorical(y_val)

    # 训练模型
    history = model.fit(X_train,y_train, epochs= 54, batch_size= 632,class_weight=class_weights, validation_data=(X_val, y_val))
    
    # 在验证集上评估模型性能并输出分类报告
    y_pred = model.predict(X_val)
    y_pred = y_pred.argmax(axis=1)
    y_true = y_val.argmax(axis=1)
    print(classification_report(y_true, y_pred))
    print("****************************************************************")
    print(sys.argv[2])
    model_save_path = sys.argv[2]
    model.save(model_save_path)

    return model_save_path

#此变量是在线训练输出的模型文件名
if 'df_val' in locals() and 'y_val' in locals():
    output_model_online_name = train_model_online(df_train, y_train, df_val, y_val)
else:
    output_model_online_name = train_model_online(df_train, y_train)