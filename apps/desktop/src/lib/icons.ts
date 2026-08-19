/**
 * OpenAmer icon library — all custom SVGs, no Tabler dependencies.
 *
 * Exports every icon name used across the app. The ~20 Tabler-only
 * utility icons (AppWindow, Archive, …) are proxied as stub exports
 * so components that import them don't break. They map to the same
 * simple SVG shapes.
 */

import {
  OaActivity as Activity,
  OaAlertCircle as AlertCircle,
  OaAlertTriangle as AlertTriangle,
  OaArrowUp as ArrowUp,
  OaArrowUpRight as ArrowUpRight,
  OaAtSign as AtSign,
  OaAttach as Attach,
  OaBell as Bell,
  OaBookmark as Bookmark,
  OaBookmark as BookmarkFilled,
  OaBrain as Brain,
  OaChat as MessageCircle,
  OaChat as MessageQuestion,
  OaCheck as CheckCircle,
  OaChevronDown as ChevronDown,
  OaChevronDown as ChevronDownIcon,
  OaChevronLeft as ChevronLeft,
  OaChevronLeft as ChevronLeftIcon,
  OaChevronRight as ChevronRight,
  OaChevronRight as ChevronRightIcon,
  OaClipboard as Clipboard,
  OaClock as Clock,
  OaCopy as Copy,
  OaClose as X,
  OaClose as XIcon,
  OaDownload as Download,
  OaExternalLink as ExternalLink,
  OaEye as Eye,
  OaEyeOff as EyeOff,
  OaFileText as FileText,
  OaFilter as Filter,
  OaFlag as Flag,
  OaFolderOpen as FolderOpen,
  OaGlobe as Globe,
  OaHash as Hash,
  OaHeart as Heart,
  OaHelpCircle as HelpCircle,
  OaImage as FileImage,
  OaImage as ImageIcon,
  OaInfo as Info,
  OaLink as Link,
  OaLink as Link2,
  OaLock as Lock,
  OaMail as Mail,
  OaMaximize as Maximize,
  OaMenu as Menu,
  OaMessage as MessageSquareText,
  OaMic as Mic,
  OaMic as MicOff,
  OaMinimize as Minimize,
  OaMoon as Moon,
  OaMore as MoreHorizontal,
  OaMore as MoreHorizontalIcon,
  OaPause as Pause,
  OaPencil as Pencil,
  OaPencil as PencilIcon,
  OaPencil as PencilLine,
  OaPin as Pin,
  OaPlay as Play,
  OaPlus as Plus,
  OaRefresh as RefreshCw,
  OaSearch as Search,
  OaSearch as SearchIcon,
  OaSend as Send,
  OaSettings as Settings,
  OaSkills as Skills,
  OaSliders as SlidersHorizontal,
  OaStar as Star,
  OaSun as Sun,
  OaTag as Tag,
  OaTerminal as Terminal,
  OaTrash as Trash2,
  OaUpload as Upload,
  OaUsers as Users,
  OaVolume as Volume2,
  OaVolume as Volume2Icon,
  OaVolumeX as VolumeX,
  OaVolumeX as VolumeXIcon,
  OaZap as Zap,
} from '@/components/ui/openamer-icons'

// ── Legacy Tabler-only utility icons ─────────────────────────
// These are rarely-used utility icons that were previously from
// @tabler/icons-react. They now use simple SVG shapes.
// If a component imports one and it's missing, add it here.

import * as React from 'react'

function stub(path: string): React.FC<{className?: string; size?: string | number; style?: React.CSSProperties}> {
  // Neural network wrapper: adds corner nodes + connection lines
  // to every icon, giving it the OpenAmer superintelligence identity.
  const C: React.FC<any> = ({ className, style }) =>
    React.createElement('svg', {
      xmlns: 'http://www.w3.org/2000/svg',
      width: 24, height: 24,
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 1.5,
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
      className,
      style,
    },
      // Neural network nodes (4 corners)
      React.createElement('circle', { cx: 4, cy: 4, r: 1.5, fill: 'currentColor' }),
      React.createElement('circle', { cx: 20, cy: 4, r: 1.5, fill: 'currentColor' }),
      React.createElement('circle', { cx: 4, cy: 20, r: 1.5, fill: 'currentColor' }),
      React.createElement('circle', { cx: 20, cy: 20, r: 1.5, fill: 'currentColor' }),
      // Connection lines (frame)
      React.createElement('line', { x1: 4, y1: 4, x2: 20, y2: 4, stroke: 'currentColor', strokeWidth: 1, opacity: 0.3 }),
      React.createElement('line', { x1: 20, y1: 4, x2: 20, y2: 20, stroke: 'currentColor', strokeWidth: 1, opacity: 0.3 }),
      React.createElement('line', { x1: 4, y1: 20, x2: 20, y2: 20, stroke: 'currentColor', strokeWidth: 1, opacity: 0.3 }),
      React.createElement('line', { x1: 4, y1: 4, x2: 4, y2: 20, stroke: 'currentColor', strokeWidth: 1, opacity: 0.3 }),
      // Diagonal connections
      React.createElement('line', { x1: 4, y1: 4, x2: 20, y2: 20, stroke: 'currentColor', strokeWidth: 0.5, opacity: 0.15 }),
      React.createElement('line', { x1: 20, y1: 4, x2: 4, y2: 20, stroke: 'currentColor', strokeWidth: 0.5, opacity: 0.15 }),
      // Center icon path
      React.createElement('path', { d: path })
    )
  C.displayName = 'OaNeural'
  return C
}

const AppWindow = stub('M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z')
const Archive = stub('M4 4h16v4H4zM5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8')
const ArchiveOff = stub('M4 4h16v4H4zM5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8M9 12h6')
const AudioLines = stub('M9 18V5M12 22V2M15 18V5M18 14V8M6 14V8')
const Box = stub('M12 3l-9 5v8l9 5 9-5V8z')
const Bug = stub('M8 3l4 4 4-4M8 21l4-4 4 4M3 8h18M3 16h18M3 12h18M8 7v3a4 4 0 0 0 8 0V7')
const BarChart3 = stub('M3 20V9M9 20V5M15 20v-7M21 20v-4')
const Check = stub('M5 13l4 4L19 7')
const CheckIcon = stub('M5 13l4 4L19 7')
const CheckCircle2 = stub('M12 22c5.5 0 10-4.5 10-10S17.5 2 12 2 2 6.5 2 12s4.5 10 10 10zM9 12l2 2 4-4')
const CircleIcon = stub('M12 22c5.5 0 10-4.5 10-10S17.5 2 12 2 2 6.5 2 12s4.5 10 10 10z')
const CircleLetterA = stub('M12 22c5.5 0 10-4.5 10-10S17.5 2 12 2 2 6.5 2 12s4.5 10 10 10zM10 16l2-8 2 8M10 14h4')
const Cloud = stub('M18 10h-1.3A5 5 0 0 0 7 11a3 3 0 0 0 0 6h11a3 3 0 0 0 0-6z')
const Command = stub('M8 4h8a4 4 0 0 1 0 8H8a4 4 0 0 1 0-8zM8 12h8a4 4 0 0 1 0 8H8a4 4 0 0 1 0-8z')
const CopyIcon = stub('M8 8V4h12v12h-4M4 8h10v12H4z')
const Cpu = stub('M6 6h12v12H6zM3 9h2M3 15h2M19 9h2M19 15h2M9 3v2M15 3v2M9 19v2M15 19v2')
const CreditCard = stub('M3 6h18v12H3zM3 10h18M7 15h4')
const GitBranch = stub('M8 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM20 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM8 6v12M8 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM8 6h4a4 4 0 0 1 4 4v6')
const GitBranchIcon = stub('M8 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM20 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM8 6v12M8 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM8 6h4a4 4 0 0 1 4 4v6')
const GitFork = stub('M8 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM20 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM12 12v6M12 12a4 4 0 0 0 4-4M12 12a4 4 0 0 1-4-4')
const GitForkIcon = stub('M8 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM20 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM12 12v6M12 12a4 4 0 0 0 4-4M12 12a4 4 0 0 1-4-4')
const Monitor = stub('M4 4h16v12H4zM8 20h8M12 16v4')
const MonitorPlay = stub('M4 4h16v12H4zM8 20h8M12 16v4M10 8l5 3-5 3z')
const MoreVertical = stub('M12 4v.01M12 12v.01M12 20v.01')
const Egg = stub('M12 22c-4 0-7-3-7-8s3-10 7-10 7 5 7 10-3 8-7 8z')
const PanelBottom = stub('M4 4h16v12H4zM4 14h16')
const LayoutDashboard = stub('M4 4h7v9H4zM13 4h7v5h-7zM13 13h7v7h-7zM4 17h5v4H4z')
const PanelLeftIcon = stub('M4 4h16v16H4zM9 4v16')
const Layers3 = stub('M12 2l9 5-9 5-9-5zM12 9l9 5-9 5-9-5zM12 16l9 5-9 5-9-5z')
const Loader2 = stub('M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83')
const Loader2Icon = stub('M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83')
const KeyRound = stub('M12 2l-3 5h-3l-2 5h4l2 8h4l2-8h4l-2-5h-3z')
const Keyboard = stub('M3 6h18v12H3zM6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 15h12')
const LogIn = stub('M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3')
const NotebookTabs = stub('M4 4h16v16H4zM4 9h16M4 15h16M9 4v16')
const Package = stub('M12 3l-9 5v8l9 5 9-5V8zM12 12l9-5M12 12v10')
const Palette = stub('M12 3a9 9 0 0 0 0 18c3 0 3-2 3-3a2 2 0 0 1 2-2c2 0 3-1 3-3a9 9 0 0 0-8-10zM8 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM14 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2z')
const StopFilled = stub('M6 6h12v12H6z')
const PawPrint = stub('M6 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 5a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM4 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM20 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 17c-3 0-5 3-5 5h10c0-2-2-5-5-5z')
const RefreshCwIcon = stub('M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8M3 3v5h5M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16M21 21v-5h-5')
const Save = stub('M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2zM17 21v-8H7v8M7 3v5h9')
const Settings2 = stub('M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z')
const Square = stub('M3 3h18v18H3z')
const Starmap = stub('M12 2l3 7 7 2-5 5 1 7-6-3-6 3 1-7-5-5 7-2z')
const SteeringWheel = stub('M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 12l5-5M12 12l-5 5M12 12l-5-5M12 12l5 5')
const Wrench = stub('M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a1 1 0 0 0 0-1.4l-1.6-1.6a1 1 0 0 0-1.4 0l-3.8 3.8zM4 20l7.5-7.5')
const ZapFilled = stub('M13 2L3 14h9l-1 8 10-12h-9l1-8z')
const ZoomIn = stub('M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0-14 0M21 21l-6-6M10 7v6M7 10h6')
const ZoomOut = stub('M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0-14 0M21 21l-6-6M7 10h6')

export type { Icon as IconComponent } from '@tabler/icons-react'

// Re-export all OpenAmer custom icons
export {
  Activity, AlertCircle, AlertTriangle,
  ArrowUp, ArrowUpRight, AtSign, Attach,
  Bell, Bookmark, BookmarkFilled, Brain,
  MessageCircle, MessageQuestion, CheckCircle,
  ChevronDown, ChevronDownIcon, ChevronLeft, ChevronLeftIcon,
  ChevronRight, ChevronRightIcon, Clipboard, Clock, Copy,
  X, XIcon, Download, ExternalLink, Eye, EyeOff,
  FileText, Filter, Flag, FolderOpen, Globe, Hash, Heart,
  HelpCircle, FileImage, ImageIcon, Info, Link, Link2,
  Lock, Mail, Maximize, Menu, MessageSquareText,
  Mic, MicOff, Minimize, Moon,
  MoreHorizontal, MoreHorizontalIcon, Pause,
  Pencil, PencilIcon, PencilLine, Pin, Play, Plus,
  RefreshCw, Search, SearchIcon, Send, Settings,
  Skills, SlidersHorizontal, Star, Sun, Tag, Terminal,
  Trash2, Upload, Users, Volume2, Volume2Icon,
  VolumeX, VolumeXIcon, Zap,
  // Legacy stub icons
  AppWindow, Archive, ArchiveOff, AudioLines, Box, Bug, BarChart3,
  Check, CheckIcon, CheckCircle2, CircleIcon, CircleLetterA,
  Cloud, Command, CopyIcon, Cpu, CreditCard,
  GitBranch, GitBranchIcon, GitFork, GitForkIcon,
  Monitor, MonitorPlay, MoreVertical, Egg,
  PanelBottom, LayoutDashboard, PanelLeftIcon, Layers3,
  Loader2, Loader2Icon, KeyRound, Keyboard, LogIn,
  NotebookTabs, Package, Palette, StopFilled, PawPrint, RefreshCwIcon,
  Save, Settings2, Square, Starmap, SteeringWheel,
  Wrench, ZapFilled, ZoomIn, ZoomOut,
}

export const iconSize = {
  '2xs': 'size-3',
  xs: 'size-3.5',
  sm: 'size-4',
  md: 'size-5',
  lg: 'size-6',
  xl: 'size-7',
  '2xl': 'size-8',
  '3xl': 'size-9',
  '4xl': 'size-10',
  '5xl': 'size-12',
  '6xl': 'size-14',
} as const

export type IconSize = keyof typeof iconSize