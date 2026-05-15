import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  padding = true,
  onClick,
}) => {
  return (
    <div
      className={`bg-white rounded-lg shadow ${padding ? 'p-4' : ''} ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
};
