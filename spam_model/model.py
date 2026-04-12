import torch.nn as nn

class SpamClassifier(nn.Module):

    def __init__(self, vocab_size):

        super().__init__()

        self.embedding = nn.Embedding(
            vocab_size,
            128,
            padding_idx=0
        )

        self.conv = nn.Conv1d(
            in_channels=128,
            out_channels=128,
            kernel_size=3,
            padding=1
        )

        self.lstm = nn.LSTM(
            input_size=128,
            hidden_size=64,
            batch_first=True
        )

        self.fc = nn.Linear(64,1)

    def forward(self,x):

        x = self.embedding(x)

        x = x.permute(0,2,1)

        x = self.conv(x)

        x = x.permute(0,2,1)

        output,(hidden,_) = self.lstm(x)

        hidden = hidden[-1]

        x = self.fc(hidden)

        return x