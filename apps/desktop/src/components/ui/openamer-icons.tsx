/**
 * OpenAmer Custom Icon Set — Hexagon/Eye/Neural Identity
 */
import * as React from 'react'

type Props = { className?: string; size?: string | number; style?: React.CSSProperties }

function Svg(children: React.ReactNode, className?: string, style?: React.CSSProperties): React.ReactElement {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      style={style} viewBox="0 0 24 24"
      width={24} xmlns="http://www.w3.org/2000/svg"
    >
      {children}
    </svg>
  )
}

const HX = 'M12 2l9 5.2v9.6L12 22l-9-5.2V7.2z'
const EY = (cx = 12, cy = 12, r = 1.5) => <circle cx={cx} cy={cy} fill="currentColor" r={r} />

function oa(children: React.ReactNode, c?: string, s?: React.CSSProperties) {
  return Svg(children, c, s)
}

export function OaChat({ className, style }: Props) { return oa(<><path d={HX} /><path d="M8 10h8M8 13h5" />{EY(12, 16)}</>, className, style) }

export function OaSkills({ className, style }: Props) { return oa(<><path d="M12 3a7 7 0 0 0-7 7v4a7 7 0 0 0 14 0v-4a7 7 0 0 0-7-7z" />{EY(8, 10)}{EY(16, 10)}{EY(12, 14)}<line x1="9" x2="11" y1="10" y2="14" /><line x1="15" x2="13" y1="10" y2="14" /></>, className, style) }

export function OaSettings({ className, style }: Props) { return oa(<><path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" /><circle cx="12" cy="12" r="4" />{EY()}</>, className, style) }

export function OaMessage({ className, style }: Props) { return oa(<><path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2z" /><circle cx="12" cy="11" fill="currentColor" r="1" /></>, className, style) }

export function OaMic({ className, style }: Props) { return oa(<><rect height="10" rx="2" width="4" x="10" y="3" /><path d="M6 12a6 6 0 0 0 12 0" /><path d="M12 19v3" /></>, className, style) }

export function OaSend({ className, style }: Props) { return oa(<><path d="M12 4v14" /><path d="M7 13l5 5 5-5" /><circle cx="12" cy="4" fill="currentColor" r="2" /></>, className, style) }

export function OaSearch({ className, style }: Props) { return oa(<><circle cx="10" cy="10" r="5" /><path d="M20 20l-4.5-4.5" />{EY(10, 10)}</>, className, style) }

export function OaPlus({ className, style }: Props) { return oa(<><path d={HX} /><line x1="12" x2="12" y1="8" y2="16" /><line x1="8" x2="16" y1="12" y2="12" /></>, className, style) }

export function OaClose({ className, style }: Props) { return oa(<><path d={HX} /><line x1="9" x2="15" y1="9" y2="15" /><line x1="15" x2="9" y1="9" y2="15" /></>, className, style) }

export function OaChevronDown({ className, style }: Props) { return oa(<><path d={HX} /><path d="M8 10l4 4 4-4" /></>, className, style) }

export function OaChevronLeft({ className, style }: Props) { return oa(<><path d={HX} /><path d="M14 8l-4 4 4 4" /></>, className, style) }

export function OaChevronRight({ className, style }: Props) { return oa(<><path d={HX} /><path d="M10 8l4 4-4 4" /></>, className, style) }

export function OaMore({ className, style }: Props) { return oa(<><path d={HX} /><circle cx="12" cy="5" fill="currentColor" r="1.5" /><circle cx="12" cy="12" fill="currentColor" r="1.5" /><circle cx="12" cy="19" fill="currentColor" r="1.5" /></>, className, style) }

export function OaPin({ className, style }: Props) { return oa(<><path d={HX} /><circle cx="12" cy="12" fill="currentColor" r="3" /></>, className, style) }

export function OaAttach({ className, style }: Props) { return oa(<><path d="M6 12l6-6a3 3 0 0 1 4.5 4.5L8 18a1.5 1.5 0 0 1-2-2l8-8" /></>, className, style) }

export function OaCheck({ className, style }: Props) { return oa(<><path d={HX} /><path d="M9 12l2 2 4-4" /></>, className, style) }

export function OaBell({ className, style }: Props) { return oa(<><path d="M18 8a6 6 0 0 0-12 0c0 4-2 6-2 6h16s-2-2-2-6" /><path d="M9 18v0a3 3 0 0 0 6 0" /></>, className, style) }

export function OaBrain({ className, style }: Props) { return oa(<><path d="M12 4a4 4 0 0 0-4 4v2a4 4 0 0 0 8 0V8a4 4 0 0 0-4-4z" /><path d="M8 14v1a3 3 0 0 0 3 3h2a3 3 0 0 0 3-3v-1" />{EY(12, 9)}</>, className, style) }

export function OaEye({ className, style }: Props) { return oa(<><path d="M12 5c-5 0-9 4-9 7s4 7 9 7 9-4 9-7-4-7-9-7z" /><circle cx="12" cy="12" fill="currentColor" r="2.5" /></>, className, style) }

export function OaEyeOff({ className, style }: Props) { return oa(<><path d="M12 5c-5 0-9 4-9 7s4 7 9 7 9-4 9-7-4-7-9-7z" /><circle cx="12" cy="12" r="2.5" /><line x1="5" x2="19" y1="5" y2="19" /></>, className, style) }

export function OaSun({ className, style }: Props) { return oa(<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" /></>, className, style) }

export function OaMoon({ className, style }: Props) { return oa(<><path d="M12 3a9 9 0 1 0 9 9c0-.5 0-1-.2-1.5a7 7 0 0 1-8.3-8.3A9 9 0 0 0 12 3z" /></>, className, style) }

export function OaActivity({ className, style }: Props) { return oa(<><path d="M3 12h4l3-8 4 16 3-8h4" /></>, className, style) }

export function OaAlertCircle({ className, style }: Props) { return oa(<><circle cx="12" cy="12" r="9" /><line x1="12" x2="12.01" y1="8" y2="8" /><line x1="12" x2="12" y1="12" y2="16" /></>, className, style) }

export function OaAlertTriangle({ className, style }: Props) { return oa(<><path d="M12 3l-9 18h18z" /><line x1="12" x2="12.01" y1="9" y2="9" /><line x1="12" x2="12" y1="13" y2="17" /></>, className, style) }

export function OaInfo({ className, style }: Props) { return oa(<><circle cx="12" cy="12" r="9" /><line x1="12" x2="12.01" y1="12" y2="12" /><line x1="12" x2="12" y1="8" y2="16" /></>, className, style) }

export function OaHelpCircle({ className, style }: Props) { return oa(<><circle cx="12" cy="12" r="9" /><path d="M10 9a2 2 0 1 1 4 0c0 1.5-2 2-2 3" /><line x1="12" x2="12.01" y1="17" y2="17" /></>, className, style) }

export function OaLock({ className, style }: Props) { return oa(<><rect height="8" rx="2" width="14" x="5" y="11" /><path d="M8 11V7a4 4 0 0 1 8 0v4" />{EY(12, 15)}</>, className, style) }

export function OaGlobe({ className, style }: Props) { return oa(<><circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="3" ry="9" /><line x1="3" x2="21" y1="12" y2="12" /></>, className, style) }

export function OaMail({ className, style }: Props) { return oa(<><rect height="14" rx="2" width="18" x="3" y="5" /><polyline points="3,7 12,13 21,7" /></>, className, style) }

export function OaFolderOpen({ className, style }: Props) { return oa(<><path d="M3 5a2 2 0 0 1 2-2h4l3 3h7a2 2 0 0 1 2 2v2" /><path d="M3 12l2-7h16l-2 7H3z" /></>, className, style) }

export function OaCopy({ className, style }: Props) { return oa(<><rect height="14" rx="2" width="14" x="8" y="8" /><path d="M4 16V4a2 2 0 0 1 2-2h10" /></>, className, style) }

export function OaDownload({ className, style }: Props) { return oa(<><path d="M12 4v12M8 12l4 4 4-4" /><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></>, className, style) }

export function OaUpload({ className, style }: Props) { return oa(<><path d="M12 16V4M8 8l4-4 4 4" /><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></>, className, style) }

export function OaTrash({ className, style }: Props) { return oa(<><line x1="4" x2="20" y1="7" y2="7" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /><path d="M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" /><path d="M9 7V4h6v3" /></>, className, style) }

export function OaUsers({ className, style }: Props) { return oa(<><circle cx="9" cy="7" r="4" /><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" /><path d="M16 3.1a4 4 0 0 1 0 7.8" /></>, className, style) }

export function OaExternalLink({ className, style }: Props) { return oa(<><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15,3 21,3 21,9" /><line x1="10" x2="21" y1="14" y2="3" /></>, className, style) }

export function OaTerminal({ className, style }: Props) { return oa(<><polyline points="5,8 9,12 5,16" /><line x1="13" x2="19" y1="16" y2="16" /><path d="M3 4h18a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" /></>, className, style) }

export function OaZap({ className, style }: Props) { return oa(<><polygon points="13,2 3,14 12,14 11,22 21,10 12,10" /></>, className, style) }

export function OaVolume({ className, style }: Props) { return oa(<><polygon points="11,5 6,9 2,9 2,15 6,15 11,19 11,5" /><path d="M15.5 8.5a5 5 0 0 1 0 7" /><path d="M18.5 5.5a9 9 0 0 1 0 13" /></>, className, style) }

export function OaVolumeX({ className, style }: Props) { return oa(<><polygon points="11,5 6,9 2,9 2,15 6,15 11,19 11,5" /><line x1="22" x2="17" y1="9" y2="14" /><line x1="17" x2="22" y1="9" y2="14" /></>, className, style) }

export function OaPencil({ className, style }: Props) { return oa(<><path d="M17 3a2.83 2.83 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5z" /></>, className, style) }

export function OaClock({ className, style }: Props) { return oa(<><circle cx="12" cy="12" r="9" /><polyline points="12,7 12,12 15,15" /></>, className, style) }

export function OaRefresh({ className, style }: Props) { return oa(<><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" /><path d="M21 21v-5h-5" /></>, className, style) }

export function OaPlay({ className, style }: Props) { return oa(<><polygon points="6,4 20,12 6,20" /></>, className, style) }

export function OaPause({ className, style }: Props) { return oa(<><rect height="16" rx="2" width="5" x="6" y="4" /><rect height="16" rx="2" width="5" x="13" y="4" /></>, className, style) }

export function OaBookmark({ className, style }: Props) { return oa(<><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" /></>, className, style) }

export function OaHash({ className, style }: Props) { return oa(<><line x1="4" x2="20" y1="9" y2="9" /><line x1="4" x2="20" y1="15" y2="15" /><line x1="8" x2="11" y1="3" y2="21" /><line x1="13" x2="16" y1="3" y2="21" /></>, className, style) }

export function OaAtSign({ className, style }: Props) { return oa(<><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="M20 12a8 8 0 0 1-8 8" /></>, className, style) }

export function OaLink({ className, style }: Props) { return oa(<><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></>, className, style) }

export function OaImage({ className, style }: Props) { return oa(<><rect height="16" rx="2" width="18" x="3" y="4" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21,15 16,10 5,21" /></>, className, style) }

export function OaFileText({ className, style }: Props) { return oa(<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14,2 14,8 20,8" /><line x1="8" x2="16" y1="13" y2="13" /><line x1="8" x2="16" y1="17" y2="17" /></>, className, style) }

export function OaClipboard({ className, style }: Props) { return oa(<><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" /><rect height="3" rx="1" width="6" x="9" y="3" /></>, className, style) }

export function OaMaximize({ className, style }: Props) { return oa(<><path d="M8 3H5a2 2 0 0 0-2 2v3" /><path d="M21 8V5a2 2 0 0 0-2-2h-3" /><path d="M16 21h3a2 2 0 0 0 2-2v-3" /><path d="M3 16v3a2 2 0 0 0 2 2h3" /><line x1="10" x2="14" y1="10" y2="14" /><circle cx="12" cy="12" fill="currentColor" r="1" /></>, className, style) }

export function OaMinimize({ className, style }: Props) { return oa(<><path d="M8 3v3a2 2 0 0 1-2 2H3" /><path d="M21 8h-3a2 2 0 0 1-2-2V3" /><path d="M16 21v-3a2 2 0 0 1 2-2h3" /><path d="M3 16h3a2 2 0 0 1 2 2v3" /></>, className, style) }

export function OaMenu({ className, style }: Props) { return oa(<><line x1="4" x2="20" y1="8" y2="8" /><line x1="4" x2="20" y1="16" y2="16" /></>, className, style) }

export function OaArrowUp({ className, style }: Props) { return oa(<><line x1="12" x2="12" y1="20" y2="4" /><polyline points="18,10 12,4 6,10" /></>, className, style) }

export function OaArrowUpRight({ className, style }: Props) { return oa(<><line x1="18" x2="6" y1="6" y2="18" /><polyline points="18,10 18,6 14,6" /></>, className, style) }

export function OaStar({ className, style }: Props) { return oa(<><polygon points="12,2 15.5,9 23,10 17,15.5 18.5,23 12,19.5 5.5,23 7,15.5 1,10 8.5,9" /></>, className, style) }

export function OaHeart({ className, style }: Props) { return oa(<><path d="M19.5 12.5l-7.5 7.5-7.5-7.5A5 5 0 0 1 12 5.5a5 5 0 0 1 7.5 7z" /></>, className, style) }

export function OaFlag({ className, style }: Props) { return oa(<><path d="M5 3v18" /><path d="M5 3h11a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5z" /></>, className, style) }

export function OaTag({ className, style }: Props) { return oa(<><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" /><line x1="7" x2="7.01" y1="7" y2="7" /></>, className, style) }

export function OaFilter({ className, style }: Props) { return oa(<><polygon points="22,3 2,3 10,12.5 10,19 14,21 14,12.5" /></>, className, style) }

export function OaSliders({ className, style }: Props) { return oa(<><line x1="4" x2="20" y1="7" y2="7" /><circle cx="7" cy="7" r="2" /><circle cx="17" cy="7" r="2" /><line x1="4" x2="20" y1="17" y2="17" /><circle cx="7" cy="17" r="2" /><circle cx="17" cy="17" r="2" /></>, className, style) }