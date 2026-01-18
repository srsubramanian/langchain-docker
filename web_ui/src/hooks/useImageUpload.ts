import { useState, useCallback, useRef } from 'react';

export interface UseImageUploadReturn {
  selectedImages: string[];
  setSelectedImages: React.Dispatch<React.SetStateAction<string[]>>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleImageSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleRemoveImage: (index: number) => void;
  handlePaste: (e: React.ClipboardEvent) => void;
  clearImages: () => void;
  openFileDialog: () => void;
}

/**
 * Hook for handling image upload functionality.
 * Supports file selection, clipboard paste, and preview management.
 */
export function useImageUpload(): UseImageUploadReturn {
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach((file) => {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        console.error('Invalid file type:', file.type);
        return;
      }

      const reader = new FileReader();
      reader.onload = () => {
        setSelectedImages((prev) => [...prev, reader.result as string]);
      };
      reader.readAsDataURL(file);
    });

    // Reset input to allow selecting the same file again
    e.target.value = '';
  }, []);

  const handleRemoveImage = useCallback((index: number) => {
    setSelectedImages((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        e.preventDefault(); // Prevent default paste behavior for images
        const file = item.getAsFile();
        if (!file) continue;

        const reader = new FileReader();
        reader.onload = () => {
          setSelectedImages((prev) => [...prev, reader.result as string]);
        };
        reader.readAsDataURL(file);
      }
    }
  }, []);

  const clearImages = useCallback(() => {
    setSelectedImages([]);
  }, []);

  const openFileDialog = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return {
    selectedImages,
    setSelectedImages,
    fileInputRef,
    handleImageSelect,
    handleRemoveImage,
    handlePaste,
    clearImages,
    openFileDialog,
  };
}
