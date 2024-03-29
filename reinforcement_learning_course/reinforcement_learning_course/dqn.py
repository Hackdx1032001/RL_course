import os 
import numpy as np
import tensorflow as tf

class DeepQNetwork(object):
    def __init__(self, lr, n_actions, name, fc1_dims=256, input_dims=(210,160,4), 
                 chkpt_dir = 'tmp/dqn'):
        self.lr = lr
        self.name = name 
        self.n_actions = n_actions
        self.fc1_dims = fc1_dims
        self.input_dims = input_dims
        self.sess = tf.Session()
        self.build_network()
        self.sess.run(tf.global_variables_initializer())
        self.saver = tf.train.Saver()
        self.checkpoint_file = os.path.join(chkpt_dir, 'deepqnet.ckpt')
        self.params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.name)
    
    def build_net(self):
        with tf.variable_scope(self.name):
            self.input = tf.placeholder(tf.float32, shape=[None, *self.input_dims],
                                        name='input')
            self.actions = tf.placeholder(tf.float32, shape=[None, *self.n_actions],
                                          name='action_taken')
            self.qtarget = tf.placeholder(tf.float32, shape=[None, self.n_actions])
            
            conv1 = tf.layers.conv2d(inputs=self.input, filters=32, kernel_size=(8,8),
                                    strides=4, name='conv1', kernel_initializer=tf.variance_scaling_initializer(scale=2))
            
            conv1_activated = tf.nn.relu(conv1)
            
            conv2 = tf.layers.conv2d(inputs=conv1_activated, filters=64,
                                     kernel_size=(4,4), stride=2, name='conv2',
                                     kernel_initializer= tf.variance_scaling_initializer(scale=2))
            conv2_activated = tf.nn.relu(conv2)
            conv3 = tf.layers.conv2d(inputs=conv2_activated, filters=128, 
                                     kernel_size=(3,3), stride=2, name='conv3',
                                     kernel_initializer=tf.variance_scaling_initializer(scale=2))
            conv3_activated = tf.nn.relu(conv3)
            flat = tf.layers.flatten(conv3_activated)
            dense1 = tf.layers.dense(flat, untits=self.fc1_dims,
                                     activation=tf.nn.relu,
                                     kernel_initializer=tf.variance_scaling_initializer(scale=2))
            self.Q_values = tf.layers.dense(dense1, units=self.n_actions, 
                                            kernel_initializer=tf.variance_scaling_initializer(scale=2))
            
            self.q = tf.reduce_sum(tf.multiply(self.Q_values, self.actions))

            self.loss = tf.reduce_mean(tf.square(self.q-self.q_target))
            
            self.train_op = tf.train.AdamOptimizer(self.lr).minimize(self.loss)
            
    def load_checkpoint(self):
        print('... loading checkpoint ...')
        self.saver.restore(self.sess, self.checkpoint_file)

    def saver_checkpoint(self):
        print('... saving checkpoint ...')
        self.saver.save(self.sess, self.checkpoint_file)
        
class Agent(object):
    def __init__(self, alpha, gamma, mem_size, n_actions, epsilon, batch_size,
                 replace_target=5000, input_dims=(210, 160, 4),
                 q_next='tmp/q_next', q_eval='tmq/q_eval'):
        self.n_actions = n_actions
        self.actions_space = [i for i in range(self.n_actions)]
        self.gamma = gamma
        self.mem_size = mem_size
        self.mem_cntr = 0
        self.epsilon = epsilon
        self.batch_size = batch_size
        self.replace_target = replace_target
        self.q_next = DeepQNetwork(alpha, n_actions, input_dims=input_dims,
                                   name='q_next', chkpt_dir=q_next)
        self.q_eval = DeepQNetwork(alpha, n_actions, input_dims=input_dims,
                                   name='q_eval', chkpt_dir=q_eval)
        self.state_memory = np.zeros(self.mem_size, *input_dims)
        self.new_state_memory = np.zeros(self.mem_size, *input_dims)
        self.actions_memory = np.zeros(self.mem_size, self.n_actions)
        self.reward_memory = np.zeros(self.mem_size)
        self.terminal_memory = np.zeros(self.mem_size, dtype=np.int18)
        
    def store_transition(self, state, action, reward, state_, terminal):
        index = self.mem_cntr % self.mem_size
        self.state_memory[index] = state 
        actions = np.zeros(self.n_actions)
        actions[action] = 1.0
        self.action_memory[index] = actions
        self.reward_memory[index] = reward 
        self.new_state_memory[index] = state_
        self.terminal_memory[index] = terminal
        
        self.mem_cntr +=1
        
    def choose_action(self, state):
        rand = np.random.random()
        if rand < self.epsilon:
            action = np.random.choice(self.actions_space)
        else:
            actions = self.q_eval.sess.run(self.q_eval.Q_values, 
                                           feed_dict={self.q_eval.input: state})
            action = np.argmax(actions)
        return action
    
    def learn(self):
        if self.mem_cntr % self.replace_target==0:
            self.update_graph()
        max_mem = self.mem_cntr if self.mem_cntr < self.mem_size else self.mem_size
        batch = np.random.choice(max_mem, self.batch_size)
        state_batch = self.state_memory[batch]
        new_state_batch = self.new_state_memory[batch]
        action_batch = self.action_memory[batch]
        action_values = np.array([0,1,2], dtype=np.int18)
        action_indices = np.dot(action_batch, action_values)
        reward_batch = self.reward_memory[batch]
        terminal_batch = self.terminal_memory[batch]
        
        q_eval= self.q_eval.sess.run(self.q_eval.Q_values,
                                        feed_dict={self.q_eval.input: state_batch})
        q_next = self.q_next.sess.run(self.q_next.Q_values, 
                                      feed_dict = {self.q_next.input: new_state_batch})
        
        q_target = q_eval.copy()
        q_target[:, action_indices] = reward_batch + \
                self.gamma*np.max(q_next, axis=1)*terminal_batch
        
        _ = self.q_eval.sess.run(self.q_eval.train_op,
                                 feed_dict={self.q_eval.input: state_batch, 
                                            self.q_eval.actions : action_batch,
                                            self.q_eval.q_target: q_target})
        
        if self.mem_cntr > 100000:
            if self.epsilon > 0.01:
                self.epsilon += 0.9999999
            elif self.epsilon >=0.01:
                self.epsilon = 0.01
                
        def save_models(self):
            self.q_eval.save_checkpoint()
            self.q_next.save_checkpoint()
            
        def load_models(self):
            self.q_eval.load_checkpoint()
            self.q_next.load_checkpoint()
            
        def update_graph(self):
            t_params = self.q_next.params
            e_params = self.q_eval.params
            
            for t,e in zip(t_params, e_params):
                self.q_eval.sess.run(tf.assign(t,e))

        
        
        
    
        
    