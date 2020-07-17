import tensorflow as tf
from umlaut import UmlautCallback

(train_images, train_labels), (test_images, test_labels) = tf.keras.datasets.fashion_mnist.load_data()
train_images = train_images / 255.
test_images = test_images / 255.

model = tf.keras.Sequential([
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(12, activation='relu'),
    tf.keras.layers.Dense(10),
    # tf.keras.layers.Softmax(),
])

cb = UmlautCallback(
    model,
    session_name='clean_session',
    # offline=True,
)

model.compile(
    optimizer='adam',
    # optimizer=tf.keras.optimizers.SGD(learning_rate=-1e5),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    # loss=tf.keras.losses.sparse_categorical_crossentropy,
    metrics=['accuracy'],
)

# train the model
model.fit(
    train_images,
    train_labels,
    epochs=15,
    batch_size=256,
    callbacks=[cb],
    # validation_data=(train_images[:100], train_labels[:100])  # cross train/val data
    validation_split=0.2,  # add validation for val metrics
)
