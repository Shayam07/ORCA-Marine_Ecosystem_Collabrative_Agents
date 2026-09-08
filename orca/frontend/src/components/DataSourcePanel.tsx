import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, ChevronDown, ChevronRight, Database, RefreshCw, AlertCircle } from 'lucide-react';
import { getSourceStatus } from '../api/client';
import type { ProviderHealth } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';

export default function DataSourcePanel() {
  const [providers, setProviders] = useState<ProviderHealth[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProviders = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSourceStatus();
      setProviders(data.providers);
    } catch (e: any) {
      setError(e.message || 'Failed to fetch provider status');
      // Set some default providers so the UI isn't empty
      setProviders([
        { provider_name: 'DEMO', status: 'HEALTHY' },
        { provider_name: 'BACKEND', status: 'UNAVAILABLE', message: 'Backend not running' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  const healthy = providers.filter((p) => p.status === 'HEALTHY').length;
  const total = providers.length;

  return (
    <Card className="border-slate-200 bg-white/95 shadow-xl backdrop-blur-xl">
      <CardHeader 
        className="cursor-pointer pb-3"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-slate-500" />
            <CardTitle className="text-xs font-bold text-slate-700 uppercase tracking-wider">DATA SOURCES</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {error ? (
              <Badge variant="destructive" className="text-xs">
                <AlertCircle className="mr-1 h-3 w-3" />
                Error
              </Badge>
            ) : (
              <Badge variant={healthy === total ? 'success' : 'secondary'} className="text-xs">
                {healthy}/{total}
              </Badge>
            )}
            {expanded ? (
              <ChevronDown className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-slate-400" />
            )}
          </div>
        </div>
      </CardHeader>
      
      {expanded && (
        <CardContent className="pt-0">
          {error && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-700">{error}</p>
              <Button 
                variant="ghost" 
                size="sm" 
                className="mt-2 text-red-600 hover:text-red-800 hover:bg-red-100"
                onClick={(e) => { e.stopPropagation(); fetchProviders(); }}
              >
                <RefreshCw className="mr-1 h-3 w-3" />
                Retry
              </Button>
            </div>
          )}
          
          <ScrollArea className="h-[200px]">
            <div className="space-y-2">
              {providers.map((provider) => (
                <div 
                  key={provider.provider_name}
                  className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    {provider.status === 'HEALTHY' ? (
                      <CheckCircle className="h-4 w-4 text-emerald-600" />
                    ) : provider.status === 'DEGRADED' ? (
                      <AlertCircle className="h-4 w-4 text-amber-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                    <div>
                      <span className="text-sm font-medium text-slate-800">
                        {provider.provider_name.replace(/_/g, ' ')}
                      </span>
                      {provider.message && (
                        <p className="text-xs text-slate-500">{provider.message}</p>
                      )}
                    </div>
                  </div>
                  <Badge 
                    variant={
                      provider.status === 'HEALTHY' ? 'success' : 
                      provider.status === 'DEGRADED' ? 'warning' : 
                      'destructive'
                    }
                    className="text-xs"
                  >
                    {provider.status}
                  </Badge>
                </div>
              ))}
            </div>
          </ScrollArea>

          <Button 
            variant="ghost" 
            size="sm" 
            className="mt-3 w-full text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            onClick={(e) => { e.stopPropagation(); fetchProviders(); }}
          >
            <RefreshCw className={`mr-2 h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
            Refresh Status
          </Button>
        </CardContent>
      )}
    </Card>
  );
}
