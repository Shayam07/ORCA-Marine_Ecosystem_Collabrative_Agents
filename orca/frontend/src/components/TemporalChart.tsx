import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { AnalysisResult } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';

interface Props {
  result: AnalysisResult;
}

export default function TemporalChart({ result }: Props) {
  // Generate demo time series data from agent results
  const generateChartData = () => {
    const days = ['Aug 1', 'Aug 5', 'Aug 9', 'Aug 13', 'Aug 17', 'Aug 21', 'Aug 25', 'Aug 28'];
    
    return days.map((day, i) => {
      const baseSST = 27 + Math.sin(i * 0.5) * 0.5 + (i > 3 ? 1.5 : 0);
      const baseChl = 1.5 - (i > 3 ? 0.4 : 0) + Math.random() * 0.2;
      const baseWind = 8 - (i > 2 ? 1.5 : 0) + Math.random() * 0.5;
      
      return {
        date: day,
        sst: parseFloat(baseSST.toFixed(2)),
        chlorophyll: parseFloat(baseChl.toFixed(2)),
        wind: parseFloat(baseWind.toFixed(2)),
      };
    });
  };

  const data = generateChartData();

  return (
    <Card className="border-slate-200 bg-white shadow-xs">
      <CardHeader className="pb-3">
        <CardTitle className="text-xs font-bold text-slate-700 uppercase tracking-wider">TEMPORAL TRENDS</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="colorSst" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f97316" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorChl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorWind" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis 
                dataKey="date" 
                stroke="#64748b"
                fontSize={10}
                tickLine={false}
              />
              <YAxis 
                stroke="#64748b"
                fontSize={10}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#ffffff', 
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  fontSize: '12px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
                labelStyle={{ color: '#0f172a', fontWeight: 'bold' }}
              />
              <Legend 
                wrapperStyle={{ fontSize: '11px', color: '#475569' }}
                iconType="circle"
              />
              <Area 
                type="monotone" 
                dataKey="sst" 
                name="SST (°C)"
                stroke="#f97316" 
                fillOpacity={1} 
                fill="url(#colorSst)" 
                strokeWidth={2}
              />
              <Area 
                type="monotone" 
                dataKey="chlorophyll" 
                name="Chl-a (mg/m³)"
                stroke="#22c55e" 
                fillOpacity={1} 
                fill="url(#colorChl)" 
                strokeWidth={2}
              />
              <Area 
                type="monotone" 
                dataKey="wind" 
                name="Wind (m/s)"
                stroke="#8b5cf6" 
                fillOpacity={1} 
                fill="url(#colorWind)" 
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
