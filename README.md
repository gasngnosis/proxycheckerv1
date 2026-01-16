# AzureCheck - Modern Proxy Validator

![AzureCheck Logo](https://via.placeholder.com/150/007BFF/FFFFFF?text=AzureCheck)

A modern web-based evolution of the legacy CLI proxy checker. AzureCheck provides a sleek, browser-based dashboard for security researchers to paste raw proxy data, extract valid endpoints, and perform high-speed validation.

## 🎨 Features

- **Azure Horizon Theme**: Sky Blue color palette with modern minimalist design
- **Real-time Validation**: WebSocket-powered live updates as proxies are tested
- **High Performance**: Python ThreadPoolExecutor with 40+ workers
- **Dual Protocol Testing**: HTTP and HTTPS connectivity verification
- **Comprehensive Reporting**: Latency measurements and exit IP resolution
- **Export Options**: Copy working proxies or download full CSV reports

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Python 3.8+
- npm or yarn

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/azurecheck.git
   cd azurecheck
   ```

2. **Install dependencies**:
   ```bash
   # Frontend dependencies
   npm install

   # Backend dependencies
   cd backend
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```

### Running the Application

```bash
# Start both frontend and backend
npm start

# Or individually:
# Frontend (port 3000)
npm run frontend

# Backend (port 8000)
cd backend && ./venv/bin/python -m uvicorn main:app --reload
```

## 📁 Project Structure

```
azurecheck/
├── backend/                  # FastAPI backend
│   ├── main.py               # Main application
│   ├── requirements.txt      # Python dependencies
│   └── venv/                 # Virtual environment
├── src/                      # React frontend
│   ├── App.jsx               # Main application component
│   ├── main.jsx              # Entry point
│   └── index.css             # Global styles
├── public/                   # Static assets
├── package.json              # Node.js dependencies
├── README.md                 # Project documentation
└── .gitignore                # Git ignore rules
```

## 🔧 Configuration

The application comes with sensible defaults:

- **Timeout**: 12 seconds per proxy test
- **Max Workers**: 40 concurrent connections
- **Test URL**: http://httpbin.org/ip

## 🎯 Usage

1. **Paste Proxy Data**: Enter raw proxy data in the textarea (supports IP:PORT format)
2. **Start Analysis**: Click "Start Analysis" to begin testing
3. **View Results**: Watch real-time progress and results
4. **Export Data**: Copy working proxies or download full CSV report

## 🛡️ Security

- Input sanitization to prevent injection attacks
- Strict timeout enforcement (12s)
- Secure WebSocket communication with HTTP fallback

## 📊 Performance

- Handles up to 500 concurrent proxy cards
- Real-time WebSocket updates
- Optimized regex pattern matching
- Efficient state management

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

MIT License

## 📬 Contact

For questions or support, please open an issue on GitHub.

---

**AzureCheck** - The modern way to validate proxies with style and speed! 🚀