import React, { useState, useEffect } from 'react';
import { 
  BookMarked, Plus, Trash2, Quote, Lightbulb, 
  CheckCircle2, Bookmark, ArrowRight, MoreVertical, 
  X, Check, ChevronDown, ChevronUp, BookOpen, Layers,
  Download
} from 'lucide-react';
import { Book, BookQuote, BookSummary } from '../types';
import { playChime } from '../utils/sound';

interface ReadingViewProps {
  selectedDate: string;
  books: Book[];
  onAddBook: (book: Omit<Book, 'id'>) => void;
  onUpdateBookProgress: (id: string, currentPage: number) => void;
  onDeleteBook: (id: string) => void;
  quotes: BookQuote[];
  onAddQuote: (quote: Omit<BookQuote, 'id' | 'createdAt'>) => void;
  onDeleteQuote: (id: string) => void;
  summaries: BookSummary[];
  onAddSummary: (summary: Omit<BookSummary, 'id' | 'createdAt'>) => void;
  onDeleteSummary: (id: string) => void;
}

export const ReadingView: React.FC<ReadingViewProps> = ({
  selectedDate,
  books,
  onAddBook,
  onUpdateBookProgress,
  onDeleteBook,
  quotes,
  onAddQuote,
  onDeleteQuote,
  summaries,
  onAddSummary,
  onDeleteSummary
}) => {
  const [readingSubTab, setReadingSubTab] = useState<'livros' | 'citacoes' | 'feynman'>('livros');

  // New Book State
  const [newTitle, setNewTitle] = useState('');
  const [newAuthor, setNewAuthor] = useState('');
  const [newTotalPages, setNewTotalPages] = useState('');
  const [showBookForm, setShowBookForm] = useState(false);

  // Active book menu dropdown (... 3 dots)
  const [activeMenuBookId, setActiveMenuBookId] = useState<string | null>(null);

  // Expanded book accordion to view its quotes & summaries
  const [expandedBookId, setExpandedBookId] = useState<string | null>(null);

  // Quick Action Modals triggered directly from book's 3-dots
  const [quickQuoteBook, setQuickQuoteBook] = useState<Book | null>(null);
  const [quickQuoteText, setQuickQuoteText] = useState('');
  const [quickQuotePage, setQuickQuotePage] = useState('');

  const [quickFeynmanBook, setQuickFeynmanBook] = useState<Book | null>(null);
  const [quickFeynmanChapter, setQuickFeynmanChapter] = useState('');
  const [quickFeynmanText, setQuickFeynmanText] = useState('');

  // Global / General forms
  const [quoteBookTitle, setQuoteBookTitle] = useState(books[0]?.title || '');
  const [quoteText, setQuoteText] = useState('');
  const [quotePage, setQuotePage] = useState('');

  const [feynmanBookTitle, setFeynmanBookTitle] = useState(books[0]?.title || '');
  const [feynmanChapter, setFeynmanChapter] = useState('');
  const [feynmanExplanation, setFeynmanExplanation] = useState('');

  useEffect(() => {
    if (books.length > 0) {
      if (!books.some(b => b.title === quoteBookTitle)) {
        setQuoteBookTitle(books[0].title);
      }
      if (!books.some(b => b.title === feynmanBookTitle)) {
        setFeynmanBookTitle(books[0].title);
      }
    }
  }, [books, quoteBookTitle, feynmanBookTitle]);

  const handleCreateBook = () => {
    if (!newTitle.trim() || !newTotalPages) return;
    onAddBook({
      title: newTitle.trim(),
      author: newAuthor.trim() || 'Autor Desconhecido',
      totalPages: Number(newTotalPages) || 100,
      currentPage: 0,
      status: 'reading',
      startDate: selectedDate
    });
    setNewTitle('');
    setNewAuthor('');
    setNewTotalPages('');
    setShowBookForm(false);
    playChime();
  };

  // Quick action from 3-dots: Save quote for specific book
  const handleSaveQuickQuote = () => {
    if (!quickQuoteBook || !quickQuoteText.trim()) return;
    onAddQuote({
      bookTitle: quickQuoteBook.title,
      quote: quickQuoteText.trim(),
      page: Number(quickQuotePage) || undefined
    });
    setQuickQuoteText('');
    setQuickQuotePage('');
    setExpandedBookId(quickQuoteBook.id);
    setQuickQuoteBook(null);
    playChime();
  };

  // Quick action from 3-dots: Save Feynman summary for specific book
  const handleSaveQuickFeynman = () => {
    if (!quickFeynmanBook || !quickFeynmanText.trim()) return;
    onAddSummary({
      bookTitle: quickFeynmanBook.title,
      chapter: quickFeynmanChapter.trim() || 'Ideia Central',
      feynmanExplanation: quickFeynmanText.trim()
    });
    setQuickFeynmanChapter('');
    setQuickFeynmanText('');
    setExpandedBookId(quickFeynmanBook.id);
    setQuickFeynmanBook(null);
    playChime();
  };

  // General quote create
  const handleCreateQuote = () => {
    if (!quoteText.trim()) return;
    onAddQuote({
      bookTitle: quoteBookTitle || books[0]?.title || 'Geral',
      quote: quoteText.trim(),
      page: Number(quotePage) || undefined
    });
    setQuoteText('');
    setQuotePage('');
    playChime();
  };

  // General summary create
  const handleCreateSummary = () => {
    if (!feynmanExplanation.trim()) return;
    onAddSummary({
      bookTitle: feynmanBookTitle || books[0]?.title || 'Geral',
      chapter: feynmanChapter || 'Capítulo Geral',
      feynmanExplanation: feynmanExplanation.trim()
    });
    setFeynmanExplanation('');
    setFeynmanChapter('');
    playChime();
  };

  // Export all books, quotes and Feynman summaries as clean .txt file
  const handleExportNotes = () => {
    let content = `======================================================\n`;
    content += `LIFE OS // ACERVO DE LEITURA, CITAÇÕES E RESUMOS\n`;
    content += `Data de Exportação: ${new Date().toLocaleString('pt-BR')}\n`;
    content += `======================================================\n\n`;

    content += `--- 1. LIVROS REGISTRADOS (${books.length}) ---\n\n`;
    books.forEach((b, i) => {
      const pct = Math.round((b.currentPage / (b.totalPages || 1)) * 100);
      content += `[${i + 1}] ${b.title}\n`;
      content += `    Autor: ${b.author}\n`;
      content += `    Progresso: ${b.currentPage} de ${b.totalPages} páginas (${pct}%)\n`;
      content += `    Status: ${b.status === 'completed' ? 'Concluído' : b.status === 'reading' ? 'Lendo' : 'Lista de Desejos'}\n`;
      if (b.startDate) content += `    Início: ${b.startDate}\n`;
      if (b.finishDate) content += `    Conclusão: ${b.finishDate}\n`;
      content += `\n`;
    });

    content += `------------------------------------------------------\n`;
    content += `--- 2. CITAÇÕES E DESTACADOS (${quotes.length}) ---\n`;
    content += `------------------------------------------------------\n\n`;
    quotes.forEach((q, i) => {
      content += `[${i + 1}] "${q.quote}"\n`;
      content += `    Livro: ${q.bookTitle}${q.page ? ` | Pág. ${q.page}` : ''}\n`;
      content += `    Salvo em: ${q.createdAt}\n\n`;
    });

    content += `------------------------------------------------------\n`;
    content += `--- 3. RESUMOS FEYNMAN (${summaries.length}) ---\n`;
    content += `------------------------------------------------------\n\n`;
    summaries.forEach((s, i) => {
      content += `[${i + 1}] ${s.bookTitle} — ${s.chapter}\n`;
      content += `    Explicação Simplificada:\n`;
      content += `    ${s.feynmanExplanation.replace(/\n/g, '\n    ')}\n`;
      content += `    Data: ${s.createdAt}\n\n`;
    });

    content += `======================================================\n`;
    content += `Fim do documento. Gerado pelo Life OS.\n`;

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `lifeos_leituras_${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    playChime();
  };

  return (
    <div className="space-y-6 pb-20">
      {/* HEADER & SUB-TABS */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-4">
        <div>
          <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white flex items-center space-x-2">
            <BookMarked className="w-4 h-4 text-white" />
            <span>Biblioteca & Retenção Ativa</span>
          </h2>
          <p className="text-xs text-neutral-500 font-mono mt-0.5">
            Acesse opções rápidas clicando em "..." em qualquer livro cadastrado
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2">
          <button
            onClick={handleExportNotes}
            className="flex items-center space-x-1.5 bg-neutral-950 border border-neutral-800 hover:border-neutral-600 px-3 py-1.5 rounded text-neutral-300 hover:text-white transition-all cursor-pointer font-mono text-xs"
            title="Exportar todas as anotações, livros e citações em formato .txt"
          >
            <Download className="w-3.5 h-3.5 text-neutral-400" />
            <span className="hidden sm:inline">Exportar</span>
            <span className="text-neutral-500">.txt</span>
          </button>

          <div className="flex items-center space-x-1 bg-neutral-950 p-1 rounded border border-neutral-800">
            {[
              { id: 'livros', label: 'Livros em Andamento' },
              { id: 'citacoes', label: 'Cofre Geral de Citações' },
              { id: 'feynman', label: 'Todos os Resumos' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setReadingSubTab(tab.id as any)}
                className={`px-3 py-1 text-xs font-mono rounded transition-colors cursor-pointer ${
                  readingSubTab === tab.id 
                    ? 'bg-white text-black font-bold' 
                    : 'text-neutral-400 hover:text-white'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 1. ABA PRINCIPAL: LIVROS COM MENU "..." EM CADA UM */}
      {readingSubTab === 'livros' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-neutral-500">
              {books.length} livro(s) cadastrado(s)
            </span>
            <button
              onClick={() => setShowBookForm(!showBookForm)}
              className="bg-white text-black px-4 py-1.5 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200 transition-colors"
            >
              {showBookForm ? 'Fechar' : '+ Novo Livro'}
            </button>
          </div>

          {showBookForm && (
            <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
              <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
                Cadastrar Novo Livro na Estante
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] font-mono text-neutral-500 block mb-1">Título</label>
                  <input
                    type="text"
                    placeholder="Ex: Meditações, Hábitos Atômicos..."
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-mono text-neutral-500 block mb-1">Autor</label>
                  <input
                    type="text"
                    placeholder="Ex: Marco Aurélio, James Clear..."
                    value={newAuthor}
                    onChange={(e) => setNewAuthor(e.target.value)}
                    className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-mono text-neutral-500 block mb-1">Total de Páginas</label>
                  <input
                    type="number"
                    placeholder="Ex: 280"
                    value={newTotalPages}
                    onChange={(e) => setNewTotalPages(e.target.value)}
                    className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                  />
                </div>
              </div>
              <button
                onClick={handleCreateBook}
                className="w-full bg-white text-black py-2.5 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
              >
                Cadastrar Livro
              </button>
            </div>
          )}

          {/* LISTA DE LIVROS COM OS TRÊS PONTINHOS (...) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {books.map((b) => {
              const progressPct = Math.min(100, Math.round((b.currentPage / b.totalPages) * 100));
              const pagesRemaining = Math.max(0, b.totalPages - b.currentPage);
              const isMenuOpen = activeMenuBookId === b.id;
              const isExpanded = expandedBookId === b.id;

              // Filter quotes and Feynman summaries linked to this specific book
              const bookQuotes = quotes.filter(q => q.bookTitle.trim().toLowerCase() === b.title.trim().toLowerCase());
              const bookSummaries = summaries.filter(s => s.bookTitle.trim().toLowerCase() === b.title.trim().toLowerCase());

              return (
                <div key={b.id} className="bg-black border border-neutral-900 rounded p-5 space-y-4 relative transition-all hover:border-neutral-800">
                  {/* Topo do card com Título, Autor e Botão de Três Pontinhos (...) */}
                  <div className="flex items-start justify-between relative">
                    <div className="pr-6">
                      <h4 className="font-mono text-sm font-bold text-white leading-snug">{b.title}</h4>
                      <span className="text-xs font-mono text-neutral-500">{b.author}</span>
                    </div>

                    {/* Botão de Três Pontinhos (...) */}
                    <div className="relative">
                      <button
                        onClick={() => setActiveMenuBookId(isMenuOpen ? null : b.id)}
                        className={`p-1.5 rounded border transition-colors ${
                          isMenuOpen 
                            ? 'bg-white text-black border-white' 
                            : 'border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-700 bg-neutral-950'
                        }`}
                        title="Opções do Livro"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>

                      {/* Dropdown Menu de Opções Rápidas */}
                      {isMenuOpen && (
                        <div className="absolute right-0 top-8 z-30 w-64 bg-neutral-950 border border-neutral-800 rounded shadow-2xl p-1.5 space-y-1 font-mono text-xs animate-in fade-in zoom-in-95">
                          <div className="px-2 py-1 text-[10px] uppercase text-neutral-500 border-b border-neutral-900">
                            Opções para: <strong className="text-white truncate block">{b.title}</strong>
                          </div>

                          <button
                            onClick={() => {
                              setActiveMenuBookId(null);
                              setQuickQuoteBook(b);
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded hover:bg-neutral-900 text-neutral-200 hover:text-white flex items-center space-x-2"
                          >
                            <Quote className="w-3.5 h-3.5 text-neutral-400" />
                            <span>+ Adicionar Citação</span>
                          </button>

                          <button
                            onClick={() => {
                              setActiveMenuBookId(null);
                              setQuickFeynmanBook(b);
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded hover:bg-neutral-900 text-neutral-200 hover:text-white flex items-center space-x-2"
                          >
                            <Lightbulb className="w-3.5 h-3.5 text-neutral-400" />
                            <span>+ Criar Resumo Feynman</span>
                          </button>

                          <button
                            onClick={() => {
                              setActiveMenuBookId(null);
                              setExpandedBookId(isExpanded ? null : b.id);
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded hover:bg-neutral-900 text-neutral-200 hover:text-white flex items-center space-x-2"
                          >
                            <Layers className="w-3.5 h-3.5 text-neutral-400" />
                            <span>{isExpanded ? 'Ocultar Anotações' : `Ver Anotações (${bookQuotes.length + bookSummaries.length})`}</span>
                          </button>

                          <div className="border-t border-neutral-900 my-1" />

                          <button
                            onClick={() => {
                              onUpdateBookProgress(b.id, b.totalPages);
                              setActiveMenuBookId(null);
                              playChime();
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded hover:bg-neutral-900 text-neutral-200 hover:text-white flex items-center space-x-2"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 text-neutral-400" />
                            <span>Marcar como Concluído</span>
                          </button>

                          <button
                            onClick={() => {
                              if (confirm(`Excluir o livro "${b.title}"?`)) {
                                onDeleteBook(b.id);
                              }
                              setActiveMenuBookId(null);
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded hover:bg-red-950/60 text-red-400 flex items-center space-x-2"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Excluir Livro</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Barra de Progresso */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-neutral-400">{b.currentPage} de {b.totalPages} págs</span>
                      <span className="text-white font-bold">{progressPct}%</span>
                    </div>
                    <div className="w-full bg-neutral-900 h-1.5 rounded-full overflow-hidden">
                      <div className="bg-white h-full transition-all duration-300" style={{ width: `${progressPct}%` }} />
                    </div>
                  </div>

                  {/* Ações Rápidas de Avanço de Página */}
                  <div className="pt-2 border-t border-neutral-900 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center space-x-1.5">
                      <span className="text-[10px] font-mono text-neutral-500">Avançar:</span>
                      <button
                        onClick={() => onUpdateBookProgress(b.id, Math.min(b.totalPages, b.currentPage + 5))}
                        className="bg-neutral-900 hover:bg-neutral-800 text-neutral-300 px-2 py-0.5 rounded text-[10px] font-mono"
                      >
                        +5p
                      </button>
                      <button
                        onClick={() => onUpdateBookProgress(b.id, Math.min(b.totalPages, b.currentPage + 10))}
                        className="bg-neutral-900 hover:bg-neutral-800 text-neutral-300 px-2 py-0.5 rounded text-[10px] font-mono"
                      >
                        +10p
                      </button>
                      <button
                        onClick={() => onUpdateBookProgress(b.id, Math.min(b.totalPages, b.currentPage + 25))}
                        className="bg-neutral-900 hover:bg-neutral-800 text-neutral-300 px-2 py-0.5 rounded text-[10px] font-mono"
                      >
                        +25p
                      </button>
                    </div>

                    <div className="flex items-center space-x-1.5">
                      <span className="text-[10px] font-mono text-neutral-500">Pág:</span>
                      <input
                        type="number"
                        value={b.currentPage}
                        onChange={(e) => onUpdateBookProgress(b.id, Number(e.target.value))}
                        className="w-16 bg-neutral-950 border border-neutral-800 rounded px-2 py-1 text-xs text-white font-mono text-center"
                      />
                    </div>
                  </div>

                  {/* Badges de Citações e Resumos Vinculados ao Livro */}
                  <div className="flex items-center justify-between pt-2 border-t border-neutral-900 text-[11px] font-mono">
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setQuickQuoteBook(b)}
                        className="text-neutral-400 hover:text-white flex items-center space-x-1 bg-neutral-950 border border-neutral-850 px-2 py-0.5 rounded hover:border-neutral-700"
                        title="Adicionar citação para este livro"
                      >
                        <Quote className="w-3 h-3" />
                        <span>{bookQuotes.length} cit.</span>
                      </button>

                      <button
                        onClick={() => setQuickFeynmanBook(b)}
                        className="text-neutral-400 hover:text-white flex items-center space-x-1 bg-neutral-950 border border-neutral-850 px-2 py-0.5 rounded hover:border-neutral-700"
                        title="Adicionar resumo Feynman para este livro"
                      >
                        <Lightbulb className="w-3 h-3" />
                        <span>{bookSummaries.length} res.</span>
                      </button>
                    </div>

                    <button
                      onClick={() => setExpandedBookId(isExpanded ? null : b.id)}
                      className="text-neutral-500 hover:text-white flex items-center space-x-1"
                    >
                      <span>{isExpanded ? 'Fechar anotações' : 'Ver tudo deste livro'}</span>
                      {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                  </div>

                  {/* PAINEL EXPANSÍVEL: CITAÇÕES E RESUMOS DESTE LIVRO ESPECÍFICO */}
                  {isExpanded && (
                    <div className="mt-3 pt-3 border-t border-neutral-800 space-y-3 font-mono">
                      <div className="flex items-center justify-between text-xs text-neutral-400">
                        <span className="font-bold text-white uppercase tracking-wider text-[10px]">
                          Cofre & Resumos de "{b.title}"
                        </span>
                        <div className="flex space-x-2">
                          <button
                            onClick={() => setQuickQuoteBook(b)}
                            className="text-[10px] text-white underline hover:text-neutral-300"
                          >
                            + Citação
                          </button>
                          <button
                            onClick={() => setQuickFeynmanBook(b)}
                            className="text-[10px] text-white underline hover:text-neutral-300"
                          >
                            + Feynman
                          </button>
                        </div>
                      </div>

                      {/* Citações do livro */}
                      {bookQuotes.length > 0 && (
                        <div className="space-y-2">
                          <span className="text-[10px] text-neutral-500 uppercase block">Citações Guardadas:</span>
                          {bookQuotes.map(q => (
                            <div key={q.id} className="bg-neutral-950 border border-neutral-900 p-2.5 rounded text-xs">
                              <p className="italic font-serif text-neutral-300">"{q.quote}"</p>
                              <div className="flex items-center justify-between mt-1 text-[10px] text-neutral-500">
                                <span>{q.page ? `Pág. ${q.page}` : 'Sem pág'}</span>
                                <button
                                  onClick={() => onDeleteQuote(q.id)}
                                  className="text-neutral-700 hover:text-red-400"
                                >
                                  Excluir
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Resumos do livro */}
                      {bookSummaries.length > 0 && (
                        <div className="space-y-2">
                          <span className="text-[10px] text-neutral-500 uppercase block">Resumos Feynman:</span>
                          {bookSummaries.map(s => (
                            <div key={s.id} className="bg-neutral-950 border border-neutral-900 p-2.5 rounded text-xs space-y-1">
                              <div className="flex items-center justify-between font-bold text-white text-[11px]">
                                <span>{s.chapter}</span>
                                <button
                                  onClick={() => onDeleteSummary(s.id)}
                                  className="text-neutral-700 hover:text-red-400 text-[10px]"
                                >
                                  Excluir
                                </button>
                              </div>
                              <p className="text-neutral-300 text-[11px] leading-relaxed">{s.feynmanExplanation}</p>
                            </div>
                          ))}
                        </div>
                      )}

                      {bookQuotes.length === 0 && bookSummaries.length === 0 && (
                        <div className="text-[11px] text-neutral-500 italic text-center py-2 bg-neutral-950 border border-neutral-900 rounded">
                          Nenhuma citação ou resumo registrado para este livro ainda. Clique nos botões acima para cadastrar em 2 segundos!
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 2. ABA: COFRE GERAL DE CITAÇÕES */}
      {readingSubTab === 'citacoes' && (
        <div className="space-y-6">
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Guardar Citação no Cofre Geral
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-2">
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Livro de Origem</label>
                <select
                  value={quoteBookTitle}
                  onChange={(e) => setQuoteBookTitle(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                >
                  {books.map(b => (
                    <option key={b.id} value={b.title}>{b.title}</option>
                  ))}
                  <option value="Geral / Outro">Geral / Outro</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Página (Opcional)</label>
                <input
                  type="number"
                  placeholder="Ex: 42"
                  value={quotePage}
                  onChange={(e) => setQuotePage(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] font-mono text-neutral-500 block mb-1">Texto da Citação</label>
              <textarea
                placeholder="Insira a frase marcante exata ou insight..."
                value={quoteText}
                onChange={(e) => setQuoteText(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded p-3 text-xs text-white font-mono h-24 resize-none"
              />
            </div>

            <button
              onClick={handleCreateQuote}
              className="bg-white text-black px-6 py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
            >
              Guardar no Cofre
            </button>
          </div>

          <div className="space-y-3">
            {quotes.map((q) => (
              <div key={q.id} className="bg-black border border-neutral-900 p-5 rounded relative group">
                <blockquote className="text-sm font-serif italic text-neutral-200 leading-relaxed">
                  "{q.quote}"
                </blockquote>
                <div className="flex items-center justify-between mt-3 pt-2 border-t border-neutral-950 font-mono text-xs text-neutral-500">
                  <span>— {q.bookTitle} {q.page && `(pág. ${q.page})`}</span>
                  <button
                    onClick={() => onDeleteQuote(q.id)}
                    className="text-neutral-700 hover:text-red-400 p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. ABA: TODOS OS RESUMOS FEYNMAN */}
      {readingSubTab === 'feynman' && (
        <div className="space-y-6">
          <div className="bg-neutral-900/40 border border-neutral-800 p-4 rounded text-xs font-mono text-neutral-300 flex items-start space-x-3">
            <Lightbulb className="w-5 h-5 text-white shrink-0 mt-0.5" />
            <div>
              <strong className="text-white">Técnica Feynman:</strong> Explique o que você aprendeu com palavras tão simples que qualquer pessoa entenderia. Se precisa de termos complicados, sintetize melhor.
            </div>
          </div>

          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Escrever Explicação em Linguagem Simples
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Livro / Fonte</label>
                <select
                  value={feynmanBookTitle}
                  onChange={(e) => setFeynmanBookTitle(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                >
                  {books.map(b => (
                    <option key={b.id} value={b.title}>{b.title}</option>
                  ))}
                  <option value="Geral / Outro">Geral / Outro</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Capítulo ou Ideia Central</label>
                <input
                  type="text"
                  placeholder="Ex: A Regra dos 2 Minutos, Dicotomia do Controle..."
                  value={feynmanChapter}
                  onChange={(e) => setFeynmanChapter(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] font-mono text-neutral-500 block mb-1">
                Explicação Simplificada (1 Parágrafo)
              </label>
              <textarea
                placeholder="Explique usando analogias simples..."
                value={feynmanExplanation}
                onChange={(e) => setFeynmanExplanation(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded p-3 text-xs text-white font-mono h-32 resize-none"
              />
            </div>

            <button
              onClick={handleCreateSummary}
              className="bg-white text-black px-6 py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
            >
              Registrar Resumo Feynman
            </button>
          </div>

          <div className="space-y-3">
            {summaries.map((s) => (
              <div key={s.id} className="bg-black border border-neutral-900 p-5 rounded space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-white">{s.chapter}</span>
                  <button
                    onClick={() => onDeleteSummary(s.id)}
                    className="text-neutral-700 hover:text-red-400 p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
                <span className="text-[11px] font-mono text-neutral-500 block">Livro: {s.bookTitle}</span>
                <p className="text-xs font-mono text-neutral-300 leading-relaxed pt-2 border-t border-neutral-950">
                  {s.feynmanExplanation}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MODAL RÁPIDO: ADICIONAR CITAÇÃO DIRETAMENTE DO LIVRO SELECIONADO NOS 3 PONTINHOS */}
      {quickQuoteBook && (
        <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-neutral-950 border border-neutral-800 rounded-lg max-w-lg w-full p-6 space-y-4 shadow-2xl font-mono">
            <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
              <div className="flex items-center space-x-2 text-white">
                <Quote className="w-4 h-4" />
                <h3 className="text-xs uppercase font-bold tracking-wider">
                  Adicionar Citação: <span className="text-neutral-400">{quickQuoteBook.title}</span>
                </h3>
              </div>
              <button
                onClick={() => setQuickQuoteBook(null)}
                className="text-neutral-500 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="text-[10px] text-neutral-500 block mb-1">Página do Livro (Opcional)</label>
              <input
                type="number"
                placeholder="Ex: 85"
                value={quickQuotePage}
                onChange={(e) => setQuickQuotePage(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
              />
            </div>

            <div>
              <label className="text-[10px] text-neutral-500 block mb-1">Frase Marcante / Citação</label>
              <textarea
                placeholder="Escreva a citação exata..."
                value={quickQuoteText}
                onChange={(e) => setQuickQuoteText(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded p-3 text-xs text-white font-mono h-28 resize-none focus:outline-none focus:border-white"
              />
            </div>

            <div className="flex space-x-2 pt-2">
              <button
                onClick={handleSaveQuickQuote}
                className="flex-1 bg-white text-black py-2 rounded text-xs font-bold uppercase hover:bg-neutral-200"
              >
                Salvar Citação
              </button>
              <button
                onClick={() => setQuickQuoteBook(null)}
                className="border border-neutral-800 text-neutral-400 hover:text-white px-4 py-2 rounded text-xs uppercase"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL RÁPIDO: CRIAR RESUMO FEYNMAN DIRETAMENTE DO LIVRO SELECIONADO NOS 3 PONTINHOS */}
      {quickFeynmanBook && (
        <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-neutral-950 border border-neutral-800 rounded-lg max-w-lg w-full p-6 space-y-4 shadow-2xl font-mono">
            <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
              <div className="flex items-center space-x-2 text-white">
                <Lightbulb className="w-4 h-4" />
                <h3 className="text-xs uppercase font-bold tracking-wider">
                  Resumo Feynman: <span className="text-neutral-400">{quickFeynmanBook.title}</span>
                </h3>
              </div>
              <button
                onClick={() => setQuickFeynmanBook(null)}
                className="text-neutral-500 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="text-[10px] text-neutral-500 block mb-1">Capítulo ou Conceito Central</label>
              <input
                type="text"
                placeholder="Ex: Como criar um novo hábito, Capítulo 3..."
                value={quickFeynmanChapter}
                onChange={(e) => setQuickFeynmanChapter(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
              />
            </div>

            <div>
              <label className="text-[10px] text-neutral-500 block mb-1">
                Explicação Simplificada em 1 Parágrafo (Método Feynman)
              </label>
              <textarea
                placeholder="Explique com palavras tão simples que uma criança entenderia..."
                value={quickFeynmanText}
                onChange={(e) => setQuickFeynmanText(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded p-3 text-xs text-white font-mono h-32 resize-none focus:outline-none focus:border-white"
              />
            </div>

            <div className="flex space-x-2 pt-2">
              <button
                onClick={handleSaveQuickFeynman}
                className="flex-1 bg-white text-black py-2 rounded text-xs font-bold uppercase hover:bg-neutral-200"
              >
                Salvar Resumo
              </button>
              <button
                onClick={() => setQuickFeynmanBook(null)}
                className="border border-neutral-800 text-neutral-400 hover:text-white px-4 py-2 rounded text-xs uppercase"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
