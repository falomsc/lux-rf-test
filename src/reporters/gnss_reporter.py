from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import dash
import plotly.graph_objects as go
from dash import dcc, html, dash_table, Input, Output, ctx
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from src.reporters.base_reporter import BaseReporter
from src.utils.logger import get_logger

logger = get_logger()


class GNSSReporter(BaseReporter):
    """GNSS 测试报告生成器"""

    def __init__(self, output_dir: str, clear_dir: bool = True):
        """

        :param output_dir:
        :param clear_dir: True 则删除 output_dir 下所有文件， False 则不删除
        """
        super().__init__()
        self._output_path = Path(output_dir)
        self._output_path.mkdir(parents=True, exist_ok=True)
        self.app = None
        if clear_dir:
            for p in self._output_path.iterdir():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()

    def generate(self, results: dict[str, list[dict]], formats: list[str] | None = None,
                 json_filename: str = "gnss_desense_result.json",
                 excel_filename: str = "gnss_desense_result.xlsx",
                 dashboard_filename: str = "gnss_desense_result.html"
                 ) -> list[str]:
        """

        :param results:
        :param formats:
        :param json_filename:
        :param excel_filename:
        :param dashboard_filename:
        :return:
        """
        output_files: list[str] = []
        formats = formats or []

        handlers = {
            "json": (self.generate_json_report, json_filename),
            "xlsx": (self.generate_excel_report, excel_filename),
            "dashboard": (self.generate_dashboard_report, dashboard_filename)
        }

        for fmt in formats:
            handler = handlers.get(fmt)
            if not handler:
                logger.warning(f"Unsupported format: {fmt}, ignored.")
                continue
            path = handler[0](results, handler[1])
            if path:
                output_files.append(path)
                logger.info(f"Generated report: {path}.")

        return output_files


    def generate_json_report(
            self,
            gnss_results: dict[str, list[dict]],
            filename: str
    ) -> str:
        """
        json 和 jsonl 格式
        :param gnss_results:
        :param filename:
        :return: 文件路径
        """
        json_path = self._output_path / filename
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(gnss_results, f, ensure_ascii=False, indent=2)

        # 为每个测试用例生成单独的 jsonl 文件
        for case_name, gnss_records in gnss_results.items():
            case_path = self._output_path / f"{case_name}.jsonl"
            with open(case_path, 'w', encoding='utf-8') as f:
                for info in gnss_records:
                    f.write(json.dumps(info, ensure_ascii=False) + '\n')

        return str(json_path)

    def generate_excel_report(
            self,
            gnss_results: dict[str, list[dict]],
            filename: str
    ) -> str:
        """

        :param gnss_results:
        :param filename:
        :return:
        """
        def format_sat(sat: dict | None) -> str | None:
            """格式化卫星信息为可读文本."""
            if not sat:
                return None
            prn = sat.get("prn")
            snr = sat.get("snr")
            const = sat.get("constellation")
            label = f"{const} {prn}" if const else (str(prn) if prn is not None else "")
            if snr is None:
                return label or None
            if label:
                return f"{label} ({snr})"
            return f"{snr}"

        def display_len(v: Any) -> int:
            if v is None:
                return 0
            if isinstance(v, float):
                s = f"{v:.2f}"
            else:
                s = str(v)
            return len(s)

        excel_path = self._output_path / filename
        # 1) 构建列描述（从第一个sheet的第一条记录推断）
        first_sheet = next(iter(gnss_results.values()))
        if not first_sheet:
            # 没有数据时也创建空文件
            wb = Workbook()
            wb.save(excel_path)
            return str(excel_path)

        sample_rec = first_sheet[0]
        columns: list[tuple[str, tuple]] = []
        # [('utc_time', ('plain', 'utc_time')), ('status', ('plain', 'status')),
        # ('overall_top4_cn', ('top4', 'overall')),
        # ('overall_gsv1', ('sat', 'overall', 0)), ('overall_gsv2', ('sat', 'overall', 1)), ('overall_gsv3', ('sat', 'overall', 2)), ('overall_gsv4', ('sat', 'overall', 3)),
        # ('gps_top4_cn', ('top4', 'gps_gsv')),
        # ('gps_gsv1', ('sat', 'gps_gsv', 0)), ('gps_gsv2', ('sat', 'gps_gsv', 1)), ('gps_gsv3', ('sat', 'gps_gsv', 2)), ('gps_gsv4', ('sat', 'gps_gsv', 3)),
        # ('bds_top4_cn', ('top4', 'bds_gsv')),
        # ('bds_gsv1', ('sat', 'bds_gsv', 0)), ('bds_gsv2', ('sat', 'bds_gsv', 1)), ('bds_gsv3', ('sat', 'bds_gsv', 2)), ('bds_gsv4', ('sat', 'bds_gsv', 3)),
        # ('gln_top4_cn', ('top4', 'gln_gsv')),
        # ('gln_gsv1', ('sat', 'gln_gsv', 0)), ('gln_gsv2', ('sat', 'gln_gsv', 1)), ('gln_gsv3', ('sat', 'gln_gsv', 2)), ('gln_gsv4', ('sat', 'gln_gsv', 3))]
        for key in sample_rec.keys():
            if key.endswith("_gsv") or key == "overall":
                base = key.replace("_gsv", "")
                columns.append((f"{base}_top4_cn", ("top4", key)))
                for i in range(4):
                    columns.append((f"{base}_gsv{i + 1}", ("sat", key, i)))
            else:
                columns.append((key, ("plain", key)))

        # 2) 样式
        center = Alignment(horizontal="center", vertical="center")
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="4F81BD")
        thin = Side(style="thin", color="D9D9D9")
        border = Border(top=thin, left=thin, right=thin, bottom=thin)

        # 3) 生成工作簿
        wb = Workbook()
        wb.remove(wb.active)

        for sheet_name, records in gnss_results.items():
            ws = wb.create_sheet(sheet_name)

            # 表头
            col_widths = [0] * len(columns)  # 列宽
            for col_idx, (header, _) in enumerate(columns, start=1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.alignment = center
                cell.font = header_font
                cell.fill = header_fill
                cell.border = border
                col_widths[col_idx - 1] = display_len(header)

            # 数据行
            for row_idx, rec in enumerate(records, start=2):
                for col_idx, (_, spec) in enumerate(columns, start=1):
                    kind = spec[0]
                    key = spec[1]

                    if kind == "plain":
                        val = rec.get(key)
                    elif kind == "top4":
                        block = rec.get(key) or {}
                        val = block.get("top4_cn")
                    else:  # "sat"
                        block = rec.get(key) or {}
                        sats = block.get("sats") or []
                        i = spec[2]
                        sat = sats[i] if i < len(sats) else None
                        val = format_sat(sat)

                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.alignment = center
                    cell.border = border

                    # # top4_cn 两位小数格式
                    # if kind == "top4" and isinstance(val, (int, float)):
                    #     cell.number_format = "0.00"

                    # 记录列宽
                    col_widths[col_idx - 1] = max(col_widths[col_idx - 1], display_len(val))

            # 冻结首行 + 自动筛选
            ws.freeze_panes = "A2"
            # last_col = get_column_letter(len(columns))
            # last_row = max(1, len(records) + 1)

            # 设置列宽（限制最大宽度避免过宽）
            for i, w in enumerate(col_widths, start=1):
                ws.column_dimensions[get_column_letter(i)].width = min(w + 2, 40)

        wb.save(excel_path)
        return str(excel_path)

    def generate_dashboard_report(
            self,
            gnss_results: dict[str, list[dict]],
            filename: str
    ) -> str:
        """
        claude opus 4.6 生成
        :param gnss_results:
        :param dashboard_filename:
        :return:
        """
        dashboard_path = self._output_path / filename
        # ── Configuration ──────────────────────────────────────────
        GSV_KEYS = ['overall', 'gps_gsv', 'bds_gsv', 'gln_gsv', 'gal_gsv']
        GSV_NAMES = {
            'overall': 'Overall', 'gps_gsv': 'GPS',
            'bds_gsv': 'BeiDou', 'gln_gsv': 'GLONASS', 'gal_gsv': 'Galileo',
        }
        GSV_COLORS = {
            'overall': '#1976D2', 'gps_gsv': '#388E3C',
            'bds_gsv': '#F57C00', 'gln_gsv': '#7B1FA2', 'gal_gsv': '#D32F2F',
        }
        CONSTELLATION_LABELS = {
            'gps': 'GPS', 'bds': 'BDS', 'gln': 'GLN', 'gal': 'GAL',
        }
        PLACEHOLDER = html.Span('← Click a point',
                                 style={'color': '#BDBDBD', 'fontSize': '12px'})

        scenarios = list(gnss_results.keys())

        # ── Helpers ────────────────────────────────────────────────
        def _fmt(v):
            return f'{v:g}'

        def extract_series(scenario):
            entries = gnss_results[scenario]
            result = {}
            for key in GSV_KEYS:
                times, cn_vals, hover_texts, indices = [], [], [], []
                for idx, entry in enumerate(entries):
                    section = entry['overall'] if key == 'overall' else entry[key]
                    cn = section['top4_cn']
                    if cn is not None:
                        times.append(entry['utc_time'])
                        cn_vals.append(cn)
                        indices.append(idx)
                        lines = [f"utc: {entry['utc_time']}",
                                 f"top4_cn: {_fmt(cn)}"]
                        for i, s in enumerate(section.get('sats', []), 1):
                            if key == 'overall' and 'constellation' in s:
                                lbl = CONSTELLATION_LABELS.get(
                                    s['constellation'],
                                    s['constellation'].upper())
                                lines.append(
                                    f"{lbl} PRN{i}: {s['prn']} "
                                    f"CN: {_fmt(s['snr'])}")
                            else:
                                lines.append(
                                    f"PRN{i}: {s['prn']} CN: {_fmt(s['snr'])}")
                        hover_texts.append('<br>'.join(lines))
                result[key] = {'times': times, 'cn': cn_vals,
                               'hover': hover_texts, 'indices': indices}
            return result

        def build_figure(key, d):
            color = GSV_COLORS[key]
            name = GSV_NAMES[key]
            fig = go.Figure()
            if d['cn']:
                fig.add_trace(go.Scatter(
                    x=d['times'], y=d['cn'],
                    mode='lines+markers',
                    marker=dict(size=5, color=color),
                    line=dict(width=1.5, color=color),
                    hovertext=d['hover'], hoverinfo='text',
                    customdata=d['indices'],
                    name=name,
                ))
                fig.update_layout(
                    title=dict(text=f'{name} — top4_cn', font=dict(size=15)),
                    xaxis_title='UTC Time',
                    yaxis_title='top4_cn (dB-Hz)',
                    height=340,
                    margin=dict(l=60, r=30, t=50, b=40),
                    hoverlabel=dict(
                        bgcolor='#FAFAFA', bordercolor='#E0E0E0',
                        font=dict(family='Consolas, "Courier New", monospace',
                                  size=13, color='#37474F'),
                        align='left'),
                    hovermode='closest',
                    plot_bgcolor='#FAFAFA',
                    xaxis=dict(gridcolor='#E0E0E0'),
                    yaxis=dict(gridcolor='#E0E0E0'),
                )
            else:
                fig.update_layout(
                    title=dict(text=f'{name} — top4_cn',
                               font=dict(size=15, color='#9E9E9E')),
                    height=180, margin=dict(l=60, r=30, t=50, b=30),
                    plot_bgcolor='#FAFAFA',
                    annotations=[dict(text='No data available', showarrow=False,
                                      xref='paper', yref='paper', x=0.5, y=0.5,
                                      font=dict(size=16, color='#BDBDBD'))],
                )
            return fig

        # ── Dash helpers ───────────────────────────────────────────
        def build_summary_table(series):
            rows = []
            for key in GSV_KEYS:
                d = series[key]
                name = GSV_NAMES[key]
                if d['cn']:
                    min_val = min(d['cn'])
                    idx = d['cn'].index(min_val)
                    avg_val = sum(d['cn']) / len(d['cn'])
                    rows.append({'Category': name,
                                 'Min top4_cn': round(min_val, 2),
                                 'Min UTC Time': d['times'][idx],
                                 'Avg top4_cn': round(avg_val, 2)})
                else:
                    rows.append({'Category': name, 'Min top4_cn': 'N/A',
                                 'Min UTC Time': 'N/A', 'Avg top4_cn': 'N/A'})
            return dash_table.DataTable(
                data=rows,
                columns=[{'name': c, 'id': c} for c in
                         ['Category', 'Min top4_cn', 'Min UTC Time',
                          'Avg top4_cn']],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'center', 'padding': '10px 14px',
                            'fontSize': '14px'},
                style_header={'fontWeight': 'bold',
                              'backgroundColor': '#37474F', 'color': 'white'},
                style_data_conditional=[
                    {'if': {'row_index': 'odd'},
                     'backgroundColor': '#F5F5F5'}],
            )

        def build_click_info(entry, section, key):
            children = [
                html.Div('📍 Point Details',
                          style={'fontWeight': 'bold', 'marginBottom': '6px',
                                 'fontSize': '14px'}),
                html.Div(f"utc: {entry['utc_time']}"),
                html.Div(f"top4_cn: {_fmt(section['top4_cn'])}"),
            ]
            for source in (entry, section):
                if 'status' in source:
                    st = source['status']
                    if isinstance(st, dict):
                        for k, v in st.items():
                            children.append(html.Div(f"{k}: {v}"))
                    else:
                        children.append(html.Div(f"status: {st}"))
                    break
            children.append(html.Hr(style={'border': 'none',
                                            'borderTop': '1px solid #E0E0E0',
                                            'margin': '8px 0'}))
            for i, s in enumerate(section.get('sats', []), 1):
                if key == 'overall' and 'constellation' in s:
                    lbl = CONSTELLATION_LABELS.get(
                        s['constellation'], s['constellation'].upper())
                    children.append(
                        html.Div(f"{lbl} PRN{i}: {s['prn']} "
                                 f"CN: {_fmt(s['snr'])}"))
                else:
                    children.append(
                        html.Div(f"PRN{i}: {s['prn']} CN: {_fmt(s['snr'])}"))
            return children

        # ══════════════════════════════════════════════════════════
        #  Save standalone HTML report (no Dash server required)
        # ══════════════════════════════════════════════════════════
        def _save_report():
            import json as _json
            import plotly.io as pio

            # ---- pre-compute all data ----
            all_series = {}
            all_figures = {}
            for sc in scenarios:
                s = extract_series(sc)
                all_series[sc] = s
                all_figures[sc] = {k: build_figure(k, s[k]) for k in GSV_KEYS}

            # ---- tab buttons ----
            tab_btns_html = ''
            for i, sc in enumerate(scenarios):
                cls = 'tab-btn active' if i == 0 else 'tab-btn'
                tab_btns_html += (
                    '<button class="' + cls + '" '
                    "onclick=\"switchTab('" + sc + "', this)\">"
                    + sc.upper() + '</button>\n')

            # ---- tab contents (tables + chart placeholders) ----
            tab_contents_html = ''
            for i, sc in enumerate(scenarios):
                disp = 'block' if i == 0 else 'none'
                tc = '<div id="tab-' + sc + '" class="tab-content" style="display:' + disp + '">\n'

                # summary table
                s = all_series[sc]
                tc += ('<table class="summary-table"><thead><tr>'
                       '<th>Category</th><th>Min top4_cn</th>'
                       '<th>Min UTC Time</th><th>Avg top4_cn</th>'
                       '</tr></thead><tbody>\n')
                for key in GSV_KEYS:
                    d = s[key]
                    name = GSV_NAMES[key]
                    if d['cn']:
                        mn = min(d['cn'])
                        mi = d['cn'].index(mn)
                        av = sum(d['cn']) / len(d['cn'])
                        tc += ('<tr><td>' + name + '</td><td>'
                               + str(round(mn, 2)) + '</td><td>'
                               + d['times'][mi] + '</td><td>'
                               + str(round(av, 2)) + '</td></tr>\n')
                    else:
                        tc += ('<tr><td>' + name
                               + '</td><td>N/A</td><td>N/A</td><td>N/A</td></tr>\n')
                tc += '</tbody></table>\n'

                # chart rows
                for key in GSV_KEYS:
                    div_id = 'chart-' + sc + '-' + key
                    clk_id = 'click-' + sc + '-' + key
                    tc += '<div class="chart-row">\n'
                    tc += '  <div class="chart-container" id="' + div_id + '"></div>\n'
                    tc += ('  <div class="click-panel" id="' + clk_id
                           + '"><span class="placeholder">&larr; Click a point</span></div>\n')
                    tc += '</div>\n'
                tc += '</div>\n'
                tab_contents_html += tc

            # ---- JSON blobs ----
            data_json = _json.dumps(gnss_results, ensure_ascii=False)
            fig_map = {}
            for sc in scenarios:
                fig_map[sc] = {}
                for key in GSV_KEYS:
                    fig_map[sc][key] = _json.loads(
                        pio.to_json(all_figures[sc][key]))
            figures_json = _json.dumps(fig_map, ensure_ascii=False)

            # ---- CSS ----
            css = """
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:'Segoe UI',Arial,sans-serif; background:#fff;
           max-width:1400px; margin:0 auto; padding-bottom:40px; }
    h2 { text-align:center; padding:18px 0 12px; color:#263238; }
    .tabs { display:flex; border-bottom:2px solid #E0E0E0; padding:0 15px; }
    .tab-btn { padding:10px 24px; border:none; background:transparent;
               cursor:pointer; font-size:15px; font-weight:600;
               color:#78909C; border-bottom:3px solid transparent; transition:.2s; }
    .tab-btn:hover { color:#263238; }
    .tab-btn.active { color:#1976D2; border-bottom-color:#1976D2; }
    .tab-content { padding:15px; }
    .summary-table { width:100%; max-width:960px; margin:0 auto 20px;
                     border-collapse:collapse; }
    .summary-table th { background:#37474F; color:#fff; padding:10px 14px;
                        font-size:14px; }
    .summary-table td { text-align:center; padding:10px 14px; font-size:14px;
                        border-bottom:1px solid #E0E0E0; }
    .summary-table tr:nth-child(odd) td { background:#F5F5F5; }
    .chart-row { display:flex; align-items:flex-start; max-width:1200px;
                 margin:0 auto 10px; }
    .chart-container { flex:1; min-width:0; }
    .click-panel { width:260px; flex-shrink:0; padding:12px;
                   margin:40px 10px 10px 5px; background:#FAFAFA;
                   border:1px solid #E0E0E0; border-radius:6px;
                   font-size:13px; font-family:Consolas,'Courier New',monospace;
                   color:#37474F; overflow-y:auto; max-height:300px;
                   line-height:1.7; }
    .placeholder { color:#BDBDBD; font-size:12px; }
    .click-title { font-weight:bold; margin-bottom:6px; font-size:14px; }
    .click-sep { border:none; border-top:1px solid #E0E0E0; margin:8px 0; }
    """

            # ---- JavaScript (plain string, no f-string) ----
            js = (
                'var GNSS_DATA='   + data_json      + ';\n'
                'var FIGURES='     + figures_json    + ';\n'
                'var GSV_KEYS='    + _json.dumps(GSV_KEYS)              + ';\n'
                'var GSV_NAMES='   + _json.dumps(GSV_NAMES)             + ';\n'
                'var CLABELS='     + _json.dumps(CONSTELLATION_LABELS)  + ';\n'
                'var SCENARIOS='   + _json.dumps(scenarios)             + ';\n'
                + r"""
    function fmt(v){return v%1===0?v.toString():parseFloat(v.toPrecision(10)).toString();}
    
    function switchTab(sc,btn){
      document.querySelectorAll('.tab-content').forEach(function(e){e.style.display='none';});
      document.querySelectorAll('.tab-btn').forEach(function(e){e.classList.remove('active');});
      document.getElementById('tab-'+sc).style.display='block';
      if(btn) btn.classList.add('active');
      renderCharts(sc);
    }
    
    function renderCharts(sc){
      GSV_KEYS.forEach(function(key){
        var id='chart-'+sc+'-'+key, el=document.getElementById(id);
        if(!el) return;
        var fig=FIGURES[sc][key];
        Plotly.react(id,fig.data,fig.layout,{displayModeBar:true,scrollZoom:true});
        el.on('plotly_click',function(data){
          var pt=data.points[0], ei=pt.customdata;
          if(Array.isArray(ei)) ei=ei[0];
          if(ei==null) return;
          var entry=GNSS_DATA[sc][ei];
          var sec=key==='overall'?entry.overall:entry[key];
          var p=document.getElementById('click-'+sc+'-'+key);
          var h='<div class="click-title">\u{1F4CD} Point Details</div>';
          h+='<div>utc: '+entry.utc_time+'</div>';
          h+='<div>top4_cn: '+fmt(sec.top4_cn)+'</div>';
          var st=entry.status||sec.status;
          if(st&&typeof st==='object'){Object.keys(st).forEach(function(k){h+='<div>'+k+': '+st[k]+'</div>';});}
          else if(st){h+='<div>status: '+st+'</div>';}
          h+='<hr class="click-sep">';
          (sec.sats||[]).forEach(function(s,i){
            if(key==='overall'&&s.constellation){
              var lb=CLABELS[s.constellation]||s.constellation.toUpperCase();
              h+='<div>'+lb+' PRN'+(i+1)+': '+s.prn+' CN: '+fmt(s.snr)+'</div>';
            }else{h+='<div>PRN'+(i+1)+': '+s.prn+' CN: '+fmt(s.snr)+'</div>';}
          });
          p.innerHTML=h;
        });
      });
    }
    
    window.addEventListener('DOMContentLoaded',function(){renderCharts(SCENARIOS[0]);});
    """)

            # ---- assemble full HTML ----
            page = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n'
                    '<meta charset="UTF-8">\n'
                    '<meta name="viewport" content="width=device-width,initial-scale=1.0">\n'
                    '<title>GNSS Signal Quality Report</title>\n'
                    '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></' + 'script>\n'
                    '<style>' + css + '</style>\n'
                    '</head>\n<body>\n'
                    '<h2>GNSS Signal Quality Report</h2>\n'
                    '<div class="tabs">\n' + tab_btns_html + '</div>\n'
                    + tab_contents_html +
                    '<script>\n' + js + '\n</' + 'script>\n'
                    '</body>\n</html>')

            with open(dashboard_path, 'w', encoding='utf-8') as f:
                f.write(page)

        # ── auto-save ──────────────────────────────────────────────
        if dashboard_path:
            _save_report()

        # ══════════════════════════════════════════════════════════
        #  Dash application (live server)
        # ══════════════════════════════════════════════════════════
        CLICK_PANEL_STYLE = {
            'width': '260px', 'flexShrink': '0', 'padding': '12px',
            'margin': '40px 10px 10px 5px', 'backgroundColor': '#FAFAFA',
            'border': '1px solid #E0E0E0', 'borderRadius': '6px',
            'fontSize': '13px',
            'fontFamily': 'Consolas, "Courier New", monospace',
            'color': '#37474F', 'overflowY': 'auto',
            'maxHeight': '300px', 'lineHeight': '1.7',
        }

        graph_rows = []
        for key in GSV_KEYS:
            graph_rows.append(
                html.Div(
                    style={'display': 'flex', 'alignItems': 'flex-start',
                           'maxWidth': '1200px', 'margin': '0 auto'},
                    children=[
                        html.Div(
                            dcc.Graph(id=f'graph-{key}',
                                      config={'displayModeBar': True,
                                              'scrollZoom': True}),
                            style={'flex': '1', 'minWidth': '0'}),
                        html.Div(id=f'click-info-{key}',
                                  children=PLACEHOLDER,
                                  style=CLICK_PANEL_STYLE),
                    ]))

        app = dash.Dash(__name__, title='GNSS Test Visualization')
        app.layout = html.Div([
            html.H2('GNSS Signal Quality Dashboard',
                     style={'textAlign': 'center', 'padding': '15px 0 10px',
                            'color': '#263238'}),
            dcc.Tabs(id='scenario-tabs', value=scenarios[0],
                     children=[dcc.Tab(label=s.upper(), value=s)
                               for s in scenarios]),
            html.Div(id='summary-table-container',
                     style={'margin': '15px auto 20px', 'maxWidth': '960px',
                            'padding': '0 15px'}),
            *graph_rows,
        ], style={
            'fontFamily': 'Segoe UI, Arial, sans-serif',
            'backgroundColor': '#FFF', 'maxWidth': '1400px',
            'margin': '0 auto', 'paddingBottom': '40px',
        })

        # ── callbacks ──────────────────────────────────────────────
        @app.callback(
            [Output('summary-table-container', 'children')]
            + [Output(f'graph-{k}', 'figure') for k in GSV_KEYS],
            Input('scenario-tabs', 'value'),
        )
        def update_dashboard(scenario):
            s = extract_series(scenario)
            return ([build_summary_table(s)]
                    + [build_figure(k, s[k]) for k in GSV_KEYS])

        def _register_click_callback(key):
            @app.callback(
                Output(f'click-info-{key}', 'children'),
                Input(f'graph-{key}', 'clickData'),
                Input('scenario-tabs', 'value'),
                prevent_initial_call=True,
            )
            def _on_click(click_data, scenario):
                triggered = [t['prop_id'].split('.')[0] for t in ctx.triggered]
                if 'scenario-tabs' in triggered or not click_data:
                    return PLACEHOLDER
                point = click_data['points'][0]
                entry_idx = point.get('customdata')
                if isinstance(entry_idx, (list, tuple)):
                    entry_idx = entry_idx[0]
                if entry_idx is None:
                    return PLACEHOLDER
                entry = gnss_results[scenario][entry_idx]
                section = (entry['overall'] if key == 'overall'
                           else entry[key])
                return build_click_info(entry, section, key)

        for _k in GSV_KEYS:
            _register_click_callback(_k)

        self.app = app
        return str(dashboard_path)
