import torch
import numpy as np
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.autograd import Variable
from tqdm import tqdm
from google_drive_downloader import GoogleDriveDownloader as gdd

class Encoder(nn.Module):

    def __init__(self,no_channels=1):
        super().__init__()

        self.conv1 = nn.Conv2d(no_channels, 16, 7, stride=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, 7, stride=3, padding=1)
        self.conv3 = nn.Conv2d(32, 64, 7)
        self.flat = nn.Flatten()
        self.mu = nn.Linear(5184, 1000)
        self.var = nn.Linear(5184, 1000)

    def forward(self, x):
        
        convolution1 = F.relu(self.conv1(x))
        convolution2 = F.relu(self.conv2(convolution1))
        convolution3 = F.relu(self.conv3(convolution2))
        Flattened = self.flat(convolution3)
        z_mu = self.mu(Flattened)
        z_var = self.var(Flattened)

        return z_mu, z_var
        
class Decoder(nn.Module):

    def __init__(self,no_channels=1):
        super().__init__()

        self.linear = nn.Linear(1000, 5184)
        self.conv4 = nn.ConvTranspose2d(64, 32, 7)
        self.conv5 = nn.ConvTranspose2d(32, 16, 7, stride=3, padding=1, output_padding=2)
        self.conv6 = nn.ConvTranspose2d(16, no_channels, 6, stride=3, padding=1, output_padding=2)

    def forward(self, x):

        hidden = self.linear(x)
        Reshaped = hidden.reshape(-1,64,9,9)
        convolution4 = F.relu(self.conv4(Reshaped))
        convolution5 = F.relu(self.conv5(convolution4))
        predicted = torch.tanh(self.conv6(convolution5))

        return predicted

class VAE(nn.Module):

    def __init__(self, enc, dec):
        super().__init__()

        self.enc = enc
        self.dec = dec

    def forward(self, x):
        
        z_mu, z_var = self.enc(x)
        std = torch.exp(z_var / 2)
        eps = torch.randn_like(std)
        x_sample = eps.mul(std).add_(z_mu)
        predicted = self.dec(x_sample)
        
        return predicted, z_mu, z_var

def train(data_path='./Data/no_sub_train.npy',
          epochs=50,
          learning_rate=2e-3,
          beta=0,
          optimizer='Adam',
          checkpoint_path='./Weights',
          pretrain=True,
          pretrain_mode='transfer',
          pretrain_model='A'):
          
        x_train = np.load(data_path)
        x_train = x_train.astype(np.float32)
        print('Data Imported')
        
        c = x_train.shape[2]
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        encoder = Encoder(no_channels=c)
        decoder = Decoder(no_channels=c)
        model = VAE(encoder, decoder).to(device)

        if pretrain == True:
        
            if pretrain_mode == 'transfer':
            
                print('Downloading Pretrained Model Weights')
                if pretrain_model == 'A':
                    gdd.download_file_from_google_drive(file_id='1US_9wOh9bGR2PqV_cQuYKkrMJn6CDpNN', dest_path=checkpoint_path + '/VAE.pth')
                else:
                    gdd.download_file_from_google_drive(file_id='1rMmgk60jT9Zr58S-81CNSiEmWDv0pKiP', dest_path=checkpoint_path + '/VAE.pth')
                    
                if torch.cuda.is_available():
                    model = torch.load(checkpoint_path + '/VAE.pth')
                else:
                    model = torch.load(checkpoint_path + '/VAE.pth', map_location=torch.device('cpu'))
                
            if pretrain_mode == 'continue':
            
                print('Importing Pretrained Model Weights')
                if torch.cuda.is_available():
                    model = torch.load(checkpoint_path + '/VAE.pth')
                else:
                    model = torch.load(checkpoint_path + '/VAE.pth', map_location=torch.device('cpu'))

        criteria = nn.MSELoss()
        
        if optimizer.lower() == 'adam':
            optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)
        elif optimizer.lower() == 'rmsprop':
            optimizer = torch.optim.RMSprop(model.parameters(), lr=learning_rate, weight_decay=1e-5)
        else:
            optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate, weight_decay=1e-5)
        
        n_epochs = epochs
        scheduler = optim.lr_scheduler.OneCycleLR(optimizer, learning_rate, epochs=n_epochs, steps_per_epoch=x_train.shape[0])

        print('Training the model!')
        loss_array = []
        for epoch in tqdm(range(1, n_epochs+1)):
            train_loss = 0.0

            for i in range(x_train.shape[0]):
                data = torch.from_numpy(x_train[i])
                if torch.cuda.is_available():
                  data = data.cuda()
                optimizer.zero_grad()
                outputs,mu,var = model(data)
                loss = criteria(outputs, data) + beta*(-0.5 * torch.sum(1 + var - mu.pow(2) - var.exp()))
                loss.backward()
                optimizer.step()
                scheduler.step()
                train_loss += loss.item()*data.size(0)

            train_loss = train_loss/x_train.shape[0]
            loss_array.append(train_loss)

            torch.save(model, checkpoint_path + '/VAE.pth')

        return loss_array
        
def evaluate(data_path='./Data/no_sub_test.npy',
          checkpoint_path='./Weights',
          out_path='./Results',
          pretrain=True,
          pretrain_mode='transfer',
          pretrain_model='A'):
          
        x_train = np.load(data_path)
        train_data = x_train.astype(np.float32)
        print('Data Imported')
        
        c = x_train.shape[2]
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        encoder = Encoder(no_channels=c)
        decoder = Decoder(no_channels=c)
        model = VAE(encoder, decoder).to(device)

        if pretrain == True:

            if pretrain_mode == 'transfer':
            
                print('Downloading Pretrained Model Weights')
                if pretrain_model == 'A':
                    gdd.download_file_from_google_drive(file_id='1US_9wOh9bGR2PqV_cQuYKkrMJn6CDpNN', dest_path=checkpoint_path + '/VAE.pth')
                else:
                    gdd.download_file_from_google_drive(file_id='1rMmgk60jT9Zr58S-81CNSiEmWDv0pKiP', dest_path=checkpoint_path + '/VAE.pth')
                    
                if torch.cuda.is_available():
                    model = torch.load(checkpoint_path + '/VAE.pth')
                else:
                    model = torch.load(checkpoint_path + '/VAE.pth', map_location=torch.device('cpu'))
                
            if pretrain_mode == 'continue':
            
                print('Importing Pretrained Model Weights')
                if torch.cuda.is_available():
                    model = torch.load(checkpoint_path + '/VAE.pth')
                else:
                    model = torch.load(checkpoint_path + '/VAE.pth', map_location=torch.device('cpu'))
                    
        else:
        
            print('Importing Pretrained Model Weights')
            if torch.cuda.is_available():
                model = torch.load(checkpoint_path + '/VAE.pth')
            else:
                model = torch.load(checkpoint_path + '/VAE.pth', map_location=torch.device('cpu'))

        criteria = nn.MSELoss()
        out = []
        for i in tqdm(range(train_data.shape[0])):
          data = torch.from_numpy(train_data[i])
          if torch.cuda.is_available():
            data = data.cuda()
          pred,z_mu,z_var = model(data)
          out.append(pred.cpu().detach().numpy())
        out = np.asarray(out)

        output = []
        for i in range(out.shape[0]):
          for j in range(out[i].shape[0]):
            output.append(out[i][j])

        output = np.asarray(output)
        np.save(out_path + '/Recon_samples.npy',output)
        
        temp1 = []
        for i in range(train_data.shape[0]):
          for j in range(train_data[i].shape[0]):
            temp1.append(train_data[i][j])
        train_data = np.asarray(temp1)
        
        losses = []
        for i in range(train_data.shape[0]):
            losses.append(criteria(torch.from_numpy(train_data[i]), torch.from_numpy(output[i])))
        
        return np.asarray(losses)