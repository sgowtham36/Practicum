


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import shutil

from absl import app as absl_app
from absl import flags
import tensorflow as tf

from utils.flags import core as flags_core
from utils.logs import hooks_helper
from utils.logs import logger
from utils.misc import model_helpers

_CSV_COLUMNS = [
    'Open','Daily','positive','negative','neutral','compound','NSEI','BSESN','N225','IXIC','std'
]

_CSV_COLUMN_DEFAULTS = [[0],[0],[0],[0],[0],[0],[0],[0],[0],[0],[0],[0]]

_NUM_EXAMPLES = {
    'train': 1250,
    'validation': 20,
}

LOSS_PREFIX = {'wide': 'linear/', 'deep': 'dnn/'}

def define_wide_deep_flags():
  """Add supervised learning flags, as well as wide-deep model type."""
  flags_core.define_base()
  flags_core.define_benchmark()

  flags.adopt_module_key_flags(flags_core)

  flags.DEFINE_enum(
      name="model_type", short_name="mt", default="wide_deep",
      enum_values=['wide', 'deep', 'wide_deep'],
      help="Select model topology.")

  flags_core.set_defaults(data_dir='./data/stock_data',
                          model_dir='./data/stock_model',
                          train_epochs=40,
                          epochs_between_evals=2,
                          batch_size=40)
  
 def build_model_columns():
  """Builds a set of wide and deep feature columns."""
  # Continuous columns
  Open = tf.feature_column.numeric_column('Open')
  daily_returns = tf.feature_column.numeric_column('Daily')
  std = tf.feature_column.numeric_column('std')
  pos = tf.feature_column.numeric_column('positive')
  neg = tf.feature_column.numeric_column('negative')
  NSE = tf.feature_column.numeric_column('NSEI')
  Nikk = tf.feature_column.numeric_column('N225')
  Nas = tf.feature_column.numeric_column('IXIC')
  BSE = tf.feature_column.numeric_column('BSESN')

  # Wide columns and deep columns.
  base_columns = [
      Open, daily_returns, NSE,std
  ]

  crossed_columns = [
      tf.feature_column.crossed_column(
          ['NSE', 'Nas','BSE','Nikk'], hash_bucket_size=1000),
      tf.feature_column.crossed_column(
          ['daily_returns','std', 'pos', 'neg'], hash_bucket_size=1000),
  ]

  wide_columns = base_columns + crossed_columns

  deep_columns = [
      Open,
      daily_returns,
      pos,
      neg,
      NSE,
      Nikk,
      Nas,
      Bse,
      std,
  ]

  return wide_columns, deep_columns

def build_estimator(model_dir, model_type):
  """Build an estimator appropriate for the given model type."""
  wide_columns, deep_columns = build_model_columns()
  hidden_units = [100, 75, 50, 25]

  # Create a tf.estimator.RunConfig to ensure the model is run on CPU, which
  # trains faster than GPU for this model.
  run_config = tf.estimator.RunConfig().replace(
      session_config=tf.ConfigProto(device_count={'GPU': 0}))

  if model_type == 'wide':
    return tf.estimator.LinearClassifier(
        model_dir=model_dir,
        feature_columns=wide_columns,
        config=run_config)
  elif model_type == 'deep':
    return tf.estimator.DNNClassifier(
        model_dir=model_dir,
        feature_columns=deep_columns,
        hidden_units=hidden_units,
        config=run_config)
  else:
    return tf.estimator.DNNLinearCombinedClassifier(
        model_dir=model_dir,
        linear_feature_columns=wide_columns,
        dnn_feature_columns=deep_columns,
        dnn_hidden_units=hidden_units,
        config=run_config)

def input_fn(data_file, num_epochs, shuffle, batch_size):
  """Generate an input function for the Estimator."""
  assert tf.gfile.Exists(data_file), (
      '%s not found. Please make sure you have run data_download.py and '
      'set the --data_dir argument to the correct path.' % data_file)

  def parse_csv(value):
    print('Parsing', data_file)
    columns = tf.decode_csv(value, record_defaults=_CSV_COLUMN_DEFAULTS)
    features = dict(zip(_CSV_COLUMNS, columns))
    labels = features.pop('income_bracket')
    return features, tf.equal(labels, '>50K')

  # Extract lines from input files using the Dataset API.
  dataset = tf.data.TextLineDataset(data_file)

  if shuffle:
    dataset = dataset.shuffle(buffer_size=_NUM_EXAMPLES['train'])

  dataset = dataset.map(parse_csv, num_parallel_calls=5)

  # We call repeat after shuffling, rather than before, to prevent separate
  # epochs from blending together.
  dataset = dataset.repeat(num_epochs)
  dataset = dataset.batch(batch_size)
  return dataset

def export_model(model, model_type, export_dir):
  """Export to SavedModel format.

  Args:
    model: Estimator object
    model_type: string indicating model type. "wide", "deep" or "wide_deep"
    export_dir: directory to export the model.
  """
  wide_columns, deep_columns = build_model_columns()
  if model_type == 'wide':
    columns = wide_columns
  elif model_type == 'deep':
    columns = deep_columns
  else:
    columns = wide_columns + deep_columns
  feature_spec = tf.feature_column.make_parse_example_spec(columns)
  example_input_fn = (
      tf.estimator.export.build_parsing_serving_input_receiver_fn(feature_spec))
  model.export_savedmodel(export_dir, example_input_fn)


def run_wide_deep(flags_obj):
  """Run Wide-Deep training and eval loop.

  Args:
    flags_obj: An object containing parsed flag values.
  """

  # Clean up the model directory if present
  shutil.rmtree(flags_obj.model_dir, ignore_errors=True)
  model = build_estimator(flags_obj.model_dir, flags_obj.model_type)

  train_file = os.path.join(flags_obj.data_dir, 'adult.data')
  test_file = os.path.join(flags_obj.data_dir, 'adult.test')

  # Train and evaluate the model every `flags.epochs_between_evals` epochs.
  def train_input_fn():
    return input_fn(
        train_file, flags_obj.epochs_between_evals, True, flags_obj.batch_size)

  def eval_input_fn():
    return input_fn(test_file, 1, False, flags_obj.batch_size)

  run_params = {
      'batch_size': flags_obj.batch_size,
      'train_epochs': flags_obj.train_epochs,
      'model_type': flags_obj.model_type,
  }

  benchmark_logger = logger.get_benchmark_logger()
  benchmark_logger.log_run_info('wide_deep', 'Census Income', run_params,
                                test_id=flags_obj.benchmark_test_id)

  loss_prefix = LOSS_PREFIX.get(flags_obj.model_type, '')
  train_hooks = hooks_helper.get_train_hooks(
      flags_obj.hooks, batch_size=flags_obj.batch_size,
      tensors_to_log={'average_loss': loss_prefix + 'head/truediv',
                      'loss': loss_prefix + 'head/weighted_loss/Sum'})

  # Train and evaluate the model every `flags.epochs_between_evals` epochs.
  for n in range(flags_obj.train_epochs // flags_obj.epochs_between_evals):
    model.train(input_fn=train_input_fn, hooks=train_hooks)
    results = model.evaluate(input_fn=eval_input_fn)

    # Display evaluation metrics
    tf.logging.info('Results at epoch %d / %d',
                    (n + 1) * flags_obj.epochs_between_evals,
                    flags_obj.train_epochs)
    tf.logging.info('-' * 60)

    for key in sorted(results):
      tf.logging.info('%s: %s' % (key, results[key]))

    benchmark_logger.log_evaluation_result(results)

    if model_helpers.past_stop_threshold(
        flags_obj.stop_threshold, results['accuracy']):
      break

  # Export the model
  if flags_obj.export_dir is not None:
    export_model(model, flags_obj.model_type, flags_obj.export_dir)


def main(_):
  with logger.benchmark_context(flags.FLAGS):
    run_wide_deep(flags.FLAGS)


if __name__ == '__main__':
  tf.logging.set_verbosity(tf.logging.INFO)
  define_wide_deep_flags()
  absl_app.run(main)
  
