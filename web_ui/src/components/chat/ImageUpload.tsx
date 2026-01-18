import { ImageIcon, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ImageUploadProps {
  selectedImages: string[];
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onImageSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onOpenFileDialog: () => void;
  onImageRemove?: (index: number) => void; // Optional, not used by this component but kept for API consistency
  disabled?: boolean;
  compact?: boolean;
}

/**
 * Image upload component with file selection button and preview grid.
 */
export function ImageUpload({
  selectedImages,
  fileInputRef,
  onImageSelect,
  onOpenFileDialog,
  disabled = false,
  compact = false,
}: ImageUploadProps) {
  return (
    <>
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        accept="image/*"
        multiple
        onChange={onImageSelect}
      />

      {/* Image upload button */}
      <Button
        type="button"
        variant="outline"
        size={compact ? 'sm' : 'icon'}
        onClick={onOpenFileDialog}
        disabled={disabled}
        title="Upload images"
        className={compact ? 'px-2' : undefined}
      >
        <ImageIcon className="h-4 w-4" />
        {compact && selectedImages.length > 0 && (
          <span className="ml-1 text-xs">{selectedImages.length}</span>
        )}
      </Button>
    </>
  );
}

interface ImagePreviewGridProps {
  images: string[];
  onRemove: (index: number) => void;
  className?: string;
}

/**
 * Grid of image previews with remove buttons.
 */
export function ImagePreviewGrid({ images, onRemove, className }: ImagePreviewGridProps) {
  if (images.length === 0) return null;

  return (
    <div className={`flex flex-wrap gap-2 p-2 bg-muted/50 rounded-lg ${className || ''}`}>
      {images.map((img, idx) => (
        <div key={idx} className="relative group">
          <img
            src={img}
            alt={`Preview ${idx + 1}`}
            className="h-16 w-16 object-cover rounded"
          />
          <button
            type="button"
            onClick={() => onRemove(idx)}
            className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      ))}
    </div>
  );
}
