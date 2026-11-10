import numpy as np
import datetime
import seaborn as sns
import matplotlib.pyplot as plt
from keras.regularizers import l1,l2
from sklearn.metrics import classification_report,confusion_matrix
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.utils import compute_class_weight



#模型构建及训练
def train_model(X_train, y_train, X_val = None, y_val = None):

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
    history = model.fit(X_train,y_train, epochs= 312, batch_size= 1234,class_weight=class_weights, validation_data=(X_val, y_val))
    
    # 绘制训练损失和验证损失
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.title('Model loss')
    plt.ylabel('Loss')
    plt.xlabel('Epoch')
    plt.legend(['Train', 'Validation'], loc='upper right')
    plt.show()

    # 绘制训练准确率和验证准确率
    plt.plot(history.history['accuracy'])
    plt.plot(history.history['val_accuracy'])
    plt.title('Model accuracy')
    plt.ylabel('Accuracy')
    plt.xlabel('Epoch')
    plt.legend(['Train', 'Validation'], loc='lower right')
    plt.show()
    
    # 在验证集上评估模型性能并输出分类报告
    y_pred = model.predict(X_val)
    y_pred = y_pred.argmax(axis=1)
    y_true = y_val.argmax(axis=1)
    print(classification_report(y_true, y_pred))

    # 混淆矩阵
    plt.figure()
    cm = confusion_matrix(y_true, y_pred)
    # 绘制热力图
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    # 设置坐标轴标签
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.xlabel('预测标签')
    plt.ylabel('真实标签')

    # 生成唯一的模型名称
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name = f"dnn_model_{timestamp}.h5"

    # 保存模型
    model.save(model_name)

    return model_name