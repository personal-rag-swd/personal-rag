import {
  ArrowLeftIcon,
  PencilIcon,
  Trash2Icon,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type NotebookHeaderProps = {
  name: string;
  tags: string[];
  onEditClick: () => void;
  onDeleteClick: () => void;
};

export function NotebookHeader({
  name,
  tags,
  onEditClick,
  onDeleteClick,
}: NotebookHeaderProps) {
  return (
    <div className="flex min-h-12 shrink-0 items-center gap-2 border-b bg-background px-3 md:px-4">
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1.5 rounded-2xl px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <ArrowLeftIcon className="size-3" />
        <span>Notebooks</span>
      </Link>

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="min-w-0">
          <h1 className="truncate font-heading text-base font-medium leading-tight text-foreground">
            {name}
          </h1>
        </div>
        {tags.length > 0 && (
          <div className="hidden items-center gap-1 lg:flex">
            {tags.slice(0, 2).map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
            {tags.length > 2 ? (
              <Badge variant="outline">+{tags.length - 2}</Badge>
            ) : null}
          </div>
        )}
      </div>

      <div className="ml-1 flex items-center gap-1">
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={onEditClick}
                aria-label="Rename notebook"
              />
            }
          >
            <PencilIcon />
          </TooltipTrigger>
          <TooltipContent side="bottom">Rename notebook</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                type="button"
                variant="destructive"
                size="icon-sm"
                onClick={onDeleteClick}
                aria-label="Delete notebook"
              />
            }
          >
            <Trash2Icon />
          </TooltipTrigger>
          <TooltipContent side="bottom">Delete notebook</TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}
