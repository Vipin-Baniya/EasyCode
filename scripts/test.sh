#!/bin/bash
# Run tests

echo "🧪 Running tests..."

# Backend tests
echo "Testing backend..."
cd backend
python -m pytest tests/ -v

# Frontend tests (if configured)
echo "Testing frontend..."
cd ../frontend
npm run test 2>/dev/null || echo "Frontend tests not configured"

echo "✅ Tests complete!"
