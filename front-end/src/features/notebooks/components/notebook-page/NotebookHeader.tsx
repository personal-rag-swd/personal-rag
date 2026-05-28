import { ArrowLeftIcon, BookOpenIcon, FileTextIcon, MessageSquareIcon, PencilIcon, TagIcon, Trash2Icon } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type NotebookHeaderProps = {
  name: string;
  tags: string[];
  documentCount: number;
  queryCount: number;
  onEditClick: () => void;
  onDeleteClick: () => void;
};

export function NotebookHeader({
  name,
  tags,
  documentCount,
  queryCount,
  onEditClick,
  onDeleteClick,
}: NotebookHeaderProps) {
  return (
    <div className="flex h-(--header-height,48px) shrink-0 items-center gap-3 border-b border-border/50 px-4 bg-background">
      <Link
        to="/dashboard"
        className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors text-xs font-medium"
      >
        <ArrowLeftIcon className="size-3.5" />
        <span>Notebooks</span>
      </Link>

      <Separator orientation="vertical" className="h-4" />

      <div className="flex min-w-0 flex-1 items-center gap-2">
        <div className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <BookOpenIcon className="size-3.5" />
        </div>
        <span className="text-sm font-semibold text-foreground truncate">{name}</span>
        {tags.length > 0 && (
          <div className="hidden sm:flex items-center gap-1 ml-1">
            {tags.slice(0, 2).map((tag) => (
              <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0 h-5">
                <TagIcon className="size-2.5 mr-1" />
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="hidden md:flex items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <FileTextIcon className="size-3" />
          <strong className="font-semibold text-foreground">{documentCount}</strong> docs
        </span>
        <span className="flex items-center gap-1">
          <MessageSquareIcon className="size-3" />
          <strong className="font-semibold text-foreground">{queryCount}</strong> queries
        </span>
      </div>

      <div className="flex items-center gap-1 ml-2">
        <Tooltip>
          <TooltipTrigger
            onClick={onEditClick}
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground cursor-pointer"
            aria-label="Rename notebook"
          >
            <PencilIcon className="size-3.5" />
          </TooltipTrigger>
          <TooltipContent side="bottom">Rename notebook</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            onClick={onDeleteClick}
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive cursor-pointer"
            aria-label="Delete notebook"
          >
            <Trash2Icon className="size-3.5" />
          </TooltipTrigger>
          <TooltipContent side="bottom">Delete notebook</TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}

