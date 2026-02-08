# UPI Fraud Detection Frontend

A React-based frontend web application for users to monitor and manage their UPI transactions with fraud detection capabilities.

## Features

### 1. **Mobile Number Authentication**
- Login using mobile number (e.g., +919876543210)
- Automatic UPI ID mapping (e.g., 9876543210@upi)
- JWT token-based authentication

### 2. **Transaction Management**
- View complete transaction history with status indicators
- Filter transactions by status: Allowed, Delayed, or Blocked
- Real-time risk assessment with color-coded indicators
- Detailed transaction information with timestamps

### 3. **Smart Notifications System**
- In-app notifications for delayed transactions requiring confirmation
- Real-time alerts for fraud detection events
- Notification panel with unread count badge
- Auto-dismissal for non-critical notifications

### 4. **Transaction Explanations**
- Detailed explanations for why transactions were delayed or blocked
- Specific fraud reasons and risk factors
- Action buttons for reviewing delayed transactions
- Expandable details for each transaction

### 5. **Selective Caching**
- Intelligent caching system for improved performance
- Configurable TTL (Time-To-Live) for different data types:
  - Dashboard: 2 minutes
  - Transactions: 5 minutes  
  - User Profile: 30 minutes
  - Notifications: 10 minutes
- Automatic cache management and eviction

## Technical Stack

- **Frontend**: React 18.3.1 with hooks
- **Routing**: React Router DOM 6.28.0
- **HTTP Client**: Axios 1.7.9
- **Styling**: Tailwind CSS classes
- **Authentication**: JWT tokens
- **Notifications**: Custom React Context API

## Project Structure

```
src/
├── components/
│   ├── Dashboard.js              # Main dashboard with stats
│   ├── TransactionHistory.js     # Transaction list with filters
│   ├── LoginScreen.js           # Mobile number login
│   ├── NotificationSystem.js     # Notification context and provider
│   ├── NotificationPanel.js     # Notification UI panel
│   └── ...other components
├── utils/
│   ├── cacheManager.js          # Selective caching system
│   └── helpers.js               # Utility functions
└── api.js                      # API integration with caching
```

## Key Features Implementation

### Transaction Status System
- **ALLOW**: Green badge - Transaction approved
- **DELAY**: Yellow badge - Pending user verification  
- **BLOCK**: Red badge - Transaction blocked

### Risk Assessment
- **Low Risk** (0-30%): Green indicator
- **Medium Risk** (30-60%): Yellow indicator
- **High Risk** (60-100%): Red indicator

### Notification Types
- **Delayed Transactions**: Require user confirmation
- **Fraud Alerts**: High-risk transactions blocked
- **System Notifications**: General app updates

## Getting Started

1. Install dependencies:
   \`\`\`bash
   npm install
   \`\`\`

2. Start development server:
   \`\`\`bash
   npm start
   \`\`\`

3. Open http://localhost:3000 in your browser

## Demo Credentials

- **Mobile**: +919876543210
- **Password**: password123
- **UPI ID**: 9876543210@upi (auto-mapped)

## API Integration

The app connects to a backend API at `http://localhost:8001` (configurable via `REACT_APP_BACKEND_URL` environment variable).

### Key Endpoints
- `POST /api/login` - User authentication
- `GET /api/user/dashboard` - Dashboard data
- `GET /api/user/transactions` - Transaction history
- `POST /api/user-decision` - Transaction confirmation

## Caching Strategy

The app implements intelligent caching to reduce API calls and improve performance:

- **Dashboard data**: Cached for 2 minutes
- **Transaction lists**: Cached for 5 minutes per filter
- **User profile**: Cached for 30 minutes
- **Notifications**: Cached for 10 minutes

Cache automatically invalidates based on TTL and can be manually cleared when needed.

## Security Features

- JWT token authentication with automatic refresh
- Secure API communication over HTTPS in production
- Input validation for phone numbers and amounts
- XSS protection through React's built-in safeguards
- No sensitive data stored in localStorage beyond tokens

## Responsive Design

- Mobile-first design approach
- Touch-friendly interface
- Adaptive layouts for different screen sizes
- PWA-ready for mobile deployment

## Performance Optimizations

- Component-level state management
- Selective re-rendering with React.memo
- Efficient list rendering with keys
- Optimized API calls with caching
- Image lazy loading and optimization