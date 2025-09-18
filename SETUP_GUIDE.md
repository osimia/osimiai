# LegalAI Setup Guide

## Quick Installation

### 1. Install Required Dependencies

```bash
# Core dependencies
pip install PyPDF2 chromadb sentence-transformers google-generativeai

# Alternative if pip doesn't work
python -m pip install PyPDF2 chromadb sentence-transformers google-generativeai

# Or install from requirements.txt
pip install -r requirements.txt
```

### 2. Environment Setup

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env
```

Add your Gemini API key to `.env`:
```
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```

### 3. Database Setup

```bash
# Create migrations
python manage.py makemigrations
python manage.py makemigrations knowledge

# Apply migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 4. Run the Server

```bash
python manage.py runserver
```

## Troubleshooting

### If PyPDF2 is missing:
```bash
pip install PyPDF2
```

### If ChromaDB is missing:
```bash
pip install chromadb
```

### If Google Generative AI is missing:
```bash
pip install google-generativeai
```

### If sentence-transformers is missing:
```bash
pip install sentence-transformers
```

## System Features

### 1. Document Management (`/knowledge/`)
- Upload PDF legal documents
- View processing status
- Manage document library

### 2. Semantic Search (`/knowledge/search/`)
- Search across all documents
- Filter by document type
- View relevance scores

### 3. AI Chat with RAG
- Chat interface with legal context
- Real-time streaming responses
- Document-based answers

## Usage Instructions

### Upload Documents
1. Go to `/knowledge/`
2. Click "Загрузить документ"
3. Select PDF file and add metadata
4. Wait for processing to complete

### Search Documents
1. Go to `/knowledge/search/`
2. Enter search query
3. Optionally filter by document type
4. View results with relevance scores

### Chat with AI
1. Go to main page (`/`)
2. Start new chat or continue existing
3. Ask questions about legal topics
4. AI will use uploaded documents for context

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Django Web    │    │   ChromaDB      │    │   Gemini AI     │
│   Interface     │◄──►│   Vector DB     │◄──►│   Embeddings    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   PDF Text      │    │   RAG Context   │
│   Database      │    │   Processing    │    │   Generation    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## API Endpoints

- `/knowledge/` - Document management interface
- `/knowledge/search/` - Search interface  
- `/knowledge/api/search/` - JSON API for search
- `/knowledge/upload/` - Document upload endpoint
- `/` - Main chat interface

## File Structure

```
windsurf-project/
├── knowledge/              # Knowledge management app
│   ├── models.py          # Document models
│   ├── views.py           # Web views
│   ├── chroma_service.py  # Vector database service
│   ├── document_processor.py # PDF processing
│   └── urls.py            # URL patterns
├── chat/                  # Chat application
│   ├── models.py          # Chat models
│   ├── views.py           # Chat views (with RAG)
│   └── urls.py            # Chat URLs
├── templates/             # HTML templates
│   ├── knowledge/         # Knowledge templates
│   └── chat/              # Chat templates
├── static/                # Static files
├── chroma_db/             # ChromaDB storage (auto-created)
└── requirements.txt       # Python dependencies
```

## Next Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Set up environment variables in `.env`
3. Run migrations: `python manage.py migrate`
4. Start server: `python manage.py runserver`
5. Upload legal documents via web interface
6. Test search and chat functionality

## Support

If you encounter issues:
1. Check that all dependencies are installed
2. Verify `.env` file has correct API key
3. Ensure database migrations are applied
4. Check server logs for error details

The system is designed to work gracefully even if some dependencies are missing, with appropriate fallbacks and error messages.
